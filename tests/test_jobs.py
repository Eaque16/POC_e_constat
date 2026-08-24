import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from econstat.config import Settings, get_settings
from econstat.database import Base, get_db
from econstat.main import app
from econstat.models import (
    AuditLog,
    Call,
    Claim,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingProfile,
    Role,
    User,
)
from econstat.schemas.claim import ClaimData, ClaimExtraction, TranscriptSegment
from econstat.services.auth import create_token
from econstat.services.jobs import (
    JobTransitionError,
    advance_job,
    claim_next_job,
    create_job,
    fail_job,
    recover_stale_jobs,
    retry_failed_job,
)
from econstat.services.pipeline import process_processing_job


def add_call_and_job(db: Session, username: str = "jobs.agent") -> tuple[User, Call, ProcessingJob]:
    user = User(username=username, hashed_password="test", role=Role.agent)
    call = Call(
        owner=user,
        audio_path="test.wav",
        audio_sha256="a" * 64,
        segments_json=[],
    )
    job = create_job(call.id, ProcessingProfile.fast)
    call.jobs.append(job)
    db.add(user)
    db.commit()
    return user, call, job


def test_claim_next_job_is_exclusive_and_progress_is_monotonic(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'claim.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _, call, first = add_call_and_job(db)
        second = create_job(call.id, ProcessingProfile.quality)
        db.add(second)
        db.commit()

        claimed_first = claim_next_job(db)
        claimed_second = claim_next_job(db)

        assert {claimed_first.id, claimed_second.id} == {first.id, second.id}
        assert claim_next_job(db) is None
        assert claimed_first.status == ProcessingJobStatus.validating_audio
        advance_job(db, claimed_first, ProcessingJobStatus.transcribing)
        with pytest.raises(JobTransitionError):
            advance_job(db, claimed_first, ProcessingJobStatus.validating_audio)


def test_stale_job_is_requeued_and_resumes_its_checkpoint(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'stale.db'}")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine, expire_on_commit=False) as db:
        _, _, job = add_call_and_job(db)
        job.status = ProcessingJobStatus.transcribing
        job.current_step = ProcessingJobStatus.transcribing.value
        job.progress_pct = 25
        job.updated_at = now - timedelta(minutes=31)
        job.locked_at = job.updated_at
        db.commit()

        assert recover_stale_jobs(db, stale_minutes=30, now=now) == 1
        assert job.status == ProcessingJobStatus.queued
        assert job.retry_count == 1
        resumed = claim_next_job(db, now=now)
        assert resumed.id == job.id
        assert resumed.status == ProcessingJobStatus.transcribing
        assert resumed.progress_pct == 25
        assert db.scalar(
            select(AuditLog).where(AuditLog.action == "job_stale_recovered")
        )


def test_failed_job_retry_keeps_checkpoint_and_enforces_limit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        _, _, job = add_call_and_job(db)
        claimed = claim_next_job(db)
        advance_job(db, claimed, ProcessingJobStatus.transcribing)
        fail_job(db, claimed, "asr_error", "modèle indisponible")

        retry_failed_job(db, claimed, max_retries=1)
        resumed = claim_next_job(db)
        assert resumed.status == ProcessingJobStatus.transcribing
        fail_job(db, resumed, "asr_error", "encore indisponible")
        with pytest.raises(JobTransitionError, match="maximal"):
            retry_failed_job(db, resumed, max_retries=1)


@pytest.mark.asyncio
async def test_pipeline_persists_each_checkpoint_with_explicit_diarization_fallback(
    tmp_path, monkeypatch
):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"synthetic")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}")
    Base.metadata.create_all(engine)

    class FakeTranscriber:
        def __init__(self, _settings, **_kwargs):
            self.last_trace = SimpleNamespace(
                as_dict=lambda: {
                    "profile": "fast",
                    "elapsed_seconds": 1.25,
                    "confidence_method": "synthetic-test",
                }
            )

        def transcribe(self, _audio):
            return [TranscriptSegment(start=0, end=1, text="plaque AB 123 CI", avg_logprob=-0.1)]

    class FakeDiarizer:
        def __init__(self, _settings):
            pass

        def run(self, _audio):
            return SimpleNamespace(
                turns=[],
                available=False,
                trace=lambda: {
                    "status": "fallback",
                    "reason": "hf_token_missing",
                    "model_source": "synthetic",
                    "elapsed_seconds": 0.0,
                    "turns": 0,
                },
            )

    class FakeExtractor:
        def __init__(self, _settings):
            pass

        async def extract(self, _transcript, *_args):
            return ClaimExtraction(
                data=ClaimData(plaque="AB 123 CI"),
                field_confidences={"plaque": 0.9},
                evidence={"plaque": "plaque AB 123 CI"},
                missing_fields=["lieu"],
                suggested_questions=["Où ?"],
                overall_confidence=0.9,
                trace={"source": "fake"},
            )

    monkeypatch.setattr(
        "econstat.services.pipeline.validate_stored_audio",
        lambda *args: SimpleNamespace(duration_seconds=1.0),
    )
    monkeypatch.setattr("econstat.services.pipeline.Transcriber", FakeTranscriber)
    monkeypatch.setattr("econstat.services.pipeline.Diarizer", FakeDiarizer)
    monkeypatch.setattr("econstat.services.pipeline.HybridExtractor", FakeExtractor)

    with Session(engine, expire_on_commit=False) as db:
        user = User(username="pipeline.agent", hashed_password="test", role=Role.agent)
        call = Call(
            owner=user,
            audio_path=str(audio),
            audio_sha256=digest,
            segments_json=[],
        )
        job = create_job(call.id, ProcessingProfile.fast)
        call.jobs.append(job)
        db.add(user)
        db.commit()
        claimed = claim_next_job(db)

        await process_processing_job(db, claimed, Settings(disable_auth=True))

        db.refresh(claimed)
        assert claimed.status == ProcessingJobStatus.ready_for_review
        assert claimed.progress_pct == 100
        assert claimed.locked_at is None
        claim = db.scalar(select(Claim).where(Claim.call_id == call.id))
        assert claim.data_json["plaque"] == "AB 123 CI"
        assert claim.evidence_json == {"plaque": "plaque AB 123 CI"}
        assert call.segments_json[0]["speaker"] == "INCONNU"
        diarization_audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "diarization_completed")
        )
        assert diarization_audit.details_json["fallback_unknown"] is True
        assert diarization_audit.details_json["reason"] == "hf_token_missing"
        transcription_audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "transcription_completed")
        )
        assert transcription_audit.details_json["elapsed_seconds"] == 1.25


@pytest.mark.asyncio
async def test_pipeline_failure_is_persisted_at_the_current_checkpoint(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline-failure.db'}")
    Base.metadata.create_all(engine)

    class FailingTranscriber:
        def __init__(self, _settings, **_kwargs):
            pass

        def transcribe(self, _audio):
            raise RuntimeError("modèle local absent")

    monkeypatch.setattr("econstat.services.pipeline.Transcriber", FailingTranscriber)
    with Session(engine, expire_on_commit=False) as db:
        _, _, job = add_call_and_job(db, "failure.agent")
        claimed = claim_next_job(db)
        advance_job(db, claimed, ProcessingJobStatus.transcribing)

        with pytest.raises(RuntimeError, match="absent"):
            await process_processing_job(db, claimed, Settings(disable_auth=True))

        db.refresh(claimed)
        assert claimed.status == ProcessingJobStatus.failed
        assert claimed.current_step == ProcessingJobStatus.transcribing.value
        assert claimed.error_code == "runtimeerror"
        assert db.scalar(select(AuditLog).where(AuditLog.action == "job_failed"))


def test_job_api_enforces_owner_and_allows_failed_retry(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api-jobs.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        owner, _, job = add_call_and_job(db, "owner.agent")
        stranger = User(username="stranger.agent", hashed_password="test", role=Role.agent)
        db.add(stranger)
        job.status = ProcessingJobStatus.failed
        job.error_code = "test"
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    def headers(user: User):
        token = create_token(user.id, user.role.value, get_settings())
        return {"Authorization": f"Bearer {token}"}

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.get(f"/api/jobs/{job.id}", headers=headers(stranger)).status_code == 404
            retry = client.post(f"/api/jobs/{job.id}/retry", headers=headers(owner))
            assert retry.status_code == 200
            assert retry.json()["status"] == "queued"
            assert len(client.get("/api/jobs", headers=headers(owner)).json()) == 1
            assert len(client.get("/api/jobs", headers=headers(stranger)).json()) == 0
    finally:
        app.dependency_overrides.clear()
