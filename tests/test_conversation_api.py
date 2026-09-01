from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from econstat.api.deps import current_user
from econstat.database import Base, get_db
from econstat.main import app
from econstat.models import Claim, ClaimStatus, Role, User


@pytest.fixture
def conversation_client(tmp_path) -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'conversation.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        user = User(username="conversation.agent", hashed_password="hash", role=Role.agent)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    def override_db():
        with factory() as db:
            yield db

    def override_user():
        with factory() as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = override_user
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_conversation_is_saved_as_one_draft_then_finalized(conversation_client):
    client, factory = conversation_client
    first = client.post(
        "/api/conversations/claims",
        json={
            "data": {"nombre_vehicules": 2},
            "transcript": ["CLIENT: Deux véhicules"],
            "field_records": {},
            "complete": False,
        },
    )
    assert first.status_code == 201
    draft = first.json()
    assert draft["status"] == "draft"
    assert draft["metrics"]["persistence_ms"] >= 0

    final = client.post(
        "/api/conversations/claims",
        json={
            "data": {"nombre_vehicules": 2, "lieu": "Cocody Angré"},
            "transcript": ["CLIENT: Deux véhicules", "CLIENT: Cocody Angré"],
            "field_records": {},
            "claim_id": draft["claim_id"],
            "complete": True,
        },
    )
    assert final.status_code == 201
    assert final.json()["claim_id"] == draft["claim_id"]
    assert final.json()["status"] == "pending_validation"

    with factory() as db:
        claims = db.query(Claim).all()
        assert len(claims) == 1
        assert claims[0].status == ClaimStatus.pending_validation
        assert claims[0].data_json["nombre_vehicules"] == 2
        assert claims[0].data_json["lieu"] == "Cocody Angré"


def test_conversation_turn_exposes_understanding_latency(conversation_client):
    client, _factory = conversation_client
    started = client.post("/api/conversations/start")
    assert started.status_code == 200
    turn = client.post(
        "/api/conversations/respond",
        json={"message": "Nguessan", "state": started.json()["state"], "asr_confidence": 0.9},
    )
    assert turn.status_code == 200
    assert turn.json()["metrics"]["understanding_ms"] >= 0
