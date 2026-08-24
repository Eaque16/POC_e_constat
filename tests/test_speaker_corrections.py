from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from econstat.config import get_settings
from econstat.database import Base, get_db
from econstat.main import app
from econstat.models import AuditLog, Call, ProcessingProfile, Role, User
from econstat.services.auth import create_token
from econstat.services.jobs import create_job


def headers(user):
    token = create_token(user.id, user.role.value, get_settings())
    return {"Authorization": f"Bearer {token}"}


def test_human_can_correct_owned_speakers_with_audit(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'speakers.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        owner = User(username="speaker.owner", hashed_password="test", role=Role.agent)
        stranger = User(username="speaker.stranger", hashed_password="test", role=Role.agent)
        call = Call(
            owner=owner,
            audio_path="synthetic.wav",
            segments_json=[
                {"start": 0, "end": 1, "text": "Bonjour", "speaker": "INCONNU"},
                {"start": 1, "end": 2, "text": "Accident", "speaker": "INCONNU"},
            ],
        )
        active_call = Call(
            owner=owner,
            audio_path="active.wav",
            segments_json=[{"start": 0, "end": 1, "text": "Test", "speaker": "INCONNU"}],
        )
        active_call.jobs.append(create_job(active_call.id, ProcessingProfile.fast))
        db.add_all([owner, stranger, call, active_call])
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            too_early = client.put(
                f"/api/calls/{active_call.id}/speakers",
                headers=headers(owner),
                json={"corrections": [{"segment_index": 0, "speaker": "AGENT"}]},
            )
            assert too_early.status_code == 409
            denied = client.put(
                f"/api/calls/{call.id}/speakers",
                headers=headers(stranger),
                json={"corrections": [{"segment_index": 0, "speaker": "AGENT"}]},
            )
            assert denied.status_code == 404

            response = client.put(
                f"/api/calls/{call.id}/speakers",
                headers=headers(owner),
                json={
                    "corrections": [
                        {"segment_index": 0, "speaker": "AGENT"},
                        {"segment_index": 1, "speaker": "ASSURE"},
                    ]
                },
            )
            assert response.status_code == 200
            assert [item["speaker"] for item in response.json()["segments"]] == [
                "AGENT",
                "ASSURE",
            ]

        with factory() as db:
            saved = db.get(Call, call.id)
            assert saved.transcript_text == "AGENT: Bonjour\nASSURE: Accident"
            audit = db.scalar(
                select(AuditLog).where(AuditLog.action == "speaker_roles_corrected")
            )
            assert audit.details_json == {"segment_indexes": [0, 1], "count": 2}
    finally:
        app.dependency_overrides.clear()


def test_speaker_correction_rejects_duplicate_or_unknown_segment(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'invalid-speakers.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        owner = User(username="invalid.owner", hashed_password="test", role=Role.agent)
        call = Call(
            owner=owner,
            audio_path="synthetic.wav",
            segments_json=[{"start": 0, "end": 1, "text": "Test", "speaker": "INCONNU"}],
        )
        db.add(owner)
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            duplicate = client.put(
                f"/api/calls/{call.id}/speakers",
                headers=headers(owner),
                json={
                    "corrections": [
                        {"segment_index": 0, "speaker": "AGENT"},
                        {"segment_index": 0, "speaker": "ASSURE"},
                    ]
                },
            )
            outside = client.put(
                f"/api/calls/{call.id}/speakers",
                headers=headers(owner),
                json={"corrections": [{"segment_index": 4, "speaker": "AGENT"}]},
            )
            invalid_role = client.put(
                f"/api/calls/{call.id}/speakers",
                headers=headers(owner),
                json={"corrections": [{"segment_index": 0, "speaker": "CLIENT"}]},
            )
        assert duplicate.status_code == 422
        assert outside.status_code == 422
        assert invalid_role.status_code == 422
    finally:
        app.dependency_overrides.clear()
