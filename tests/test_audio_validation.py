import hashlib
import io
import uuid
import wave
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from econstat.config import get_settings
from econstat.database import Base, get_db
from econstat.main import app
from econstat.models import AuditLog, Call, Role, User
from econstat.services.auth import create_token


def wav_bytes(duration_seconds: float = 0.2, sample_rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


@pytest.fixture
def audio_client(
    tmp_path, monkeypatch
) -> Generator[tuple[TestClient, sessionmaker, User], None, None]:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("MAX_AUDIO_MB", "1")
    monkeypatch.setenv("MAX_AUDIO_DURATION_SECONDS", "1")
    get_settings.cache_clear()

    engine = create_engine(
        f"sqlite:///{tmp_path / 'audio.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        user = User(username="audio.agent", hashed_password="test", role=Role.agent)
        db.add(user)
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, factory, user
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def auth_headers(user: User) -> dict[str, str]:
    token = create_token(user.id, user.role.value, get_settings())
    return {"Authorization": f"Bearer {token}"}


def test_valid_audio_is_stored_under_uuid_with_hash_and_audit(audio_client):
    client, factory, user = audio_client
    content = wav_bytes()

    response = client.post(
        "/api/calls",
        headers=auth_headers(user),
        files={"audio": ("../../nom-client.wav", content, "audio/wav")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert uuid.UUID(payload["id"])
    assert payload["sha256"] == hashlib.sha256(content).hexdigest()
    assert payload["duration_seconds"] == pytest.approx(0.2, abs=0.02)

    with factory() as db:
        call = db.get(Call, payload["id"])
        assert call is not None
        path = Path(call.audio_path)
        assert path.name == f"{call.id}.wav"
        assert "nom-client" not in str(path)
        assert path.read_bytes() == content
        assert call.audio_sha256 == payload["sha256"]
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == call.id,
                AuditLog.action == "audio_uploaded",
            )
        )
        assert audit is not None
        assert audit.details_json["size_bytes"] == len(content)


@pytest.mark.parametrize(
    ("filename", "content", "mime_type", "expected_code"),
    [
        ("audio.exe", wav_bytes(), "audio/wav", "audio_extension_not_allowed"),
        ("audio.wav", wav_bytes(), "text/plain", "audio_mime_not_allowed"),
        ("audio.wav", b"not an audio file", "audio/wav", "audio_container_invalid"),
        ("audio.mp3", wav_bytes(), "audio/mpeg", "audio_extension_mismatch"),
        ("audio.wav", b"", "audio/wav", "audio_empty"),
    ],
)
def test_invalid_upload_is_rejected_and_cleaned(
    audio_client, filename, content, mime_type, expected_code
):
    client, factory, user = audio_client

    response = client.post(
        "/api/calls",
        headers=auth_headers(user),
        files={"audio": (filename, content, mime_type)},
    )

    assert response.status_code in {415, 422}
    assert response.json()["detail"]["code"] == expected_code
    with factory() as db:
        assert db.scalar(select(func.count(Call.id))) == 0
        rejection = db.scalar(
            select(AuditLog).where(AuditLog.action == "audio_upload_rejected")
        )
        assert rejection is not None
        assert rejection.details_json == {"error_code": expected_code}
    upload_dir = Path(get_settings().upload_dir)
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_oversized_upload_is_rejected_before_probe(audio_client):
    client, factory, user = audio_client
    content = b"0" * (1024 * 1024 + 1)

    response = client.post(
        "/api/calls",
        headers=auth_headers(user),
        files={"audio": ("large.wav", content, "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "audio_size_exceeded"
    with factory() as db:
        assert db.scalar(select(func.count(Call.id))) == 0


def test_audio_over_duration_limit_is_rejected(audio_client):
    client, factory, user = audio_client

    response = client.post(
        "/api/calls",
        headers=auth_headers(user),
        files={"audio": ("long.wav", wav_bytes(1.2), "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "audio_duration_exceeded"
    with factory() as db:
        assert db.scalar(select(func.count(Call.id))) == 0


def test_missing_ffprobe_returns_clear_service_error(audio_client, monkeypatch):
    client, factory, user = audio_client
    monkeypatch.setattr("econstat.services.audio_validation.shutil.which", lambda _: None)

    response = client.post(
        "/api/calls",
        headers=auth_headers(user),
        files={"audio": ("audio.wav", wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ffprobe_unavailable"
    with factory() as db:
        assert db.scalar(select(func.count(Call.id))) == 0
