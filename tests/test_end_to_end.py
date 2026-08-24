import asyncio
import io
import json
import wave
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from econstat import worker
from econstat.api import routes
from econstat.config import get_settings
from econstat.database import Base, get_db
from econstat.main import app
from econstat.mock_server import app as mock_app
from econstat.mock_server import reference_index, store
from econstat.models import AuditLog, Claim, ProcessingJob, ProcessingJobStatus, Role, User
from econstat.schemas.claim import TranscriptSegment
from econstat.services.auth import hash_password
from econstat.services.econsta import EConstaClient as RealEConstaClient
from econstat.services.jobs import claim_next_job
from econstat.services.pipeline import process_processing_job


def synthetic_wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()


class SyntheticTranscriber:
    def __init__(self, _settings, **_kwargs):
        self.last_trace = SimpleNamespace(
            as_dict=lambda: {
                "profile": "fast",
                "elapsed_seconds": 0.01,
                "confidence_method": "synthetic-e2e",
            }
        )

    def transcribe(self, _audio):
        return [
            TranscriptSegment(
                start=0,
                end=4,
                text=(
                    "Bonjour service sinistre. Je suis Awa Koné, ma plaque est "
                    "AB 1234 CI et l'accident a eu lieu à Cocody."
                ),
                avg_logprob=-0.1,
                confidence=0.9,
            )
        ]


@pytest.fixture
def e2e_environment(
    tmp_path, monkeypatch
) -> Generator[tuple[TestClient, sessionmaker], None, None]:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GENERATED_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    monkeypatch.setenv("ENABLE_LLM", "false")
    monkeypatch.setenv("ALLOW_MODEL_DOWNLOADS", "false")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    get_settings.cache_clear()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'e2e.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [
                User(
                    username="e2e.agent",
                    hashed_password=hash_password("Agent-secret"),
                    role=Role.agent,
                ),
                User(
                    username="e2e.manager",
                    hashed_password=hash_password("Manager-secret"),
                    role=Role.responsable,
                ),
            ]
        )
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    store.clear()
    reference_index.clear()
    with TestClient(app) as client:
        yield client, factory
    store.clear()
    reference_index.clear()
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_complete_call_to_json_and_mock_workflow(e2e_environment, monkeypatch):
    client, factory = e2e_environment
    agent_headers = login_headers(client, "e2e.agent", "Agent-secret")
    manager_headers = login_headers(client, "e2e.manager", "Manager-secret")
    monkeypatch.setattr("econstat.services.pipeline.Transcriber", SyntheticTranscriber)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(
        routes,
        "EConstaClient",
        lambda settings: RealEConstaClient(
            settings, transport=httpx.ASGITransport(app=mock_app)
        ),
    )

    uploaded = client.post(
        "/api/calls",
        headers=agent_headers,
        data={"profile": "fast"},
        files={"audio": ("appel-synthetique.wav", synthetic_wav(), "audio/wav")},
    )
    assert uploaded.status_code == 201
    job_id = uploaded.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}", headers=agent_headers).json()["status"] == "queued"

    assert asyncio.run(worker.run_once()) is True

    job_response = client.get(f"/api/jobs/{job_id}", headers=agent_headers)
    assert job_response.json()["status"] == "ready_for_review"
    assert job_response.json()["progress_pct"] == 100
    claims = client.get("/api/claims", headers=agent_headers).json()
    assert len(claims) == 1
    claim_id = claims[0]["id"]
    call_id = claims[0]["call_id"]
    review = client.get(f"/api/claims/{claim_id}", headers=agent_headers).json()
    assert review["current_data"]["plaque"] == "AB 1234 CI"
    assert review["evidence"]["plaque"] in client.get(
        f"/api/calls/{call_id}", headers=agent_headers
    ).json()["transcript_text"]

    correction = dict(review["current_data"])
    correction["nom_assure"] = "Awa Koné corrigé"
    assert client.put(
        f"/api/claims/{claim_id}", headers=agent_headers, json={"data": correction}
    ).status_code == 200
    assert client.put(
        f"/api/calls/{call_id}/speakers",
        headers=agent_headers,
        json={"corrections": [{"segment_index": 0, "speaker": "AGENT"}]},
    ).status_code == 200
    assert client.get(
        f"/api/claims/{claim_id}/export-json", headers=agent_headers
    ).status_code == 409
    assert client.post(f"/api/claims/{claim_id}/send", headers=agent_headers).status_code == 409

    assert client.post(
        f"/api/claims/{claim_id}/validate", headers=agent_headers
    ).status_code == 200
    exported = client.get(
        f"/api/claims/{claim_id}/export-json", headers=agent_headers
    )
    payload = json.loads(Path(exported.json()["path"]).read_text(encoding="utf-8"))
    assert payload["declaration"]["nom_assure"] == "Awa Koné corrigé"
    assert payload["validation_humaine"]["validee"] is True

    sent = client.post(f"/api/claims/{claim_id}/send", headers=agent_headers)
    replay = client.post(f"/api/claims/{claim_id}/send", headers=agent_headers)
    assert sent.status_code == 200
    assert replay.json()["id"] == sent.json()["id"]
    assert replay.json()["idempotent_replay"] is True

    dashboard = client.get("/api/dashboard", headers=manager_headers).json()
    assert dashboard["appels"] == 1
    assert dashboard["dossiers_envoyes"] == 1
    assert dashboard["taux_dossiers_corriges_pct"] == 100
    with factory() as db:
        actions = set(db.scalars(select(AuditLog.action)).all())
    assert {
        "audio_uploaded",
        "job_started",
        "transcription_completed",
        "diarization_completed",
        "extraction_completed",
        "human_edit",
        "human_validation",
        "json_export_generated",
        "sent_to_econsta",
    }.issubset(actions)


def test_failed_transcription_can_resume_from_checkpoint(e2e_environment, monkeypatch):
    client, factory = e2e_environment
    headers = login_headers(client, "e2e.agent", "Agent-secret")

    class FailingTranscriber:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, _audio):
            raise RuntimeError("modèle synthétiquement indisponible")

    uploaded = client.post(
        "/api/calls",
        headers=headers,
        files={"audio": ("reprise.wav", synthetic_wav(), "audio/wav")},
    ).json()
    monkeypatch.setattr("econstat.services.pipeline.Transcriber", FailingTranscriber)
    with factory() as db:
        job = claim_next_job(db)
        with pytest.raises(RuntimeError, match="indisponible"):
            asyncio.run(process_processing_job(db, job, get_settings()))

    failed = client.get(f"/api/jobs/{uploaded['job_id']}", headers=headers).json()
    assert failed["status"] == "failed"
    assert failed["current_step"] == "transcribing"
    assert client.post(
        f"/api/jobs/{uploaded['job_id']}/retry", headers=headers
    ).status_code == 200

    monkeypatch.setattr("econstat.services.pipeline.Transcriber", SyntheticTranscriber)
    with factory() as db:
        resumed = claim_next_job(db)
        assert resumed.current_step == "transcribing"
        asyncio.run(process_processing_job(db, resumed, get_settings()))
        final = db.get(ProcessingJob, uploaded["job_id"])
        claim = db.scalar(select(Claim).where(Claim.call_id == final.call_id))
    assert final.status == ProcessingJobStatus.ready_for_review
    assert final.retry_count == 1
    assert claim is not None
