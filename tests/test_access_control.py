from collections.abc import Generator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from econstat.config import get_settings
from econstat.database import Base, get_db
from econstat.main import app
from econstat.models import AuditLog, Call, Claim, ClaimStatus, Role, User
from econstat.services.auth import create_token, hash_password

AGENT_A_HASH = hash_password("AgentA-secret")
AGENT_B_HASH = hash_password("AgentB-secret")
MANAGER_HASH = hash_password("Manager-secret")


@dataclass
class SecurityData:
    agent_a: User
    agent_b: User
    manager: User
    claim_a: Claim
    claim_b: Claim
    call_a: Call
    call_b: Call


@pytest.fixture
def security_client(
    tmp_path,
) -> Generator[tuple[TestClient, sessionmaker, SecurityData], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'security.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    with factory() as db:
        agent_a = User(
            username="agent.a", hashed_password=AGENT_A_HASH, role=Role.agent
        )
        agent_b = User(
            username="agent.b", hashed_password=AGENT_B_HASH, role=Role.agent
        )
        manager = User(
            username="manager",
            hashed_password=MANAGER_HASH,
            role=Role.responsable,
        )
        call_a = Call(owner=agent_a, audio_path="demo://a", segments_json=[])
        call_b = Call(owner=agent_b, audio_path="demo://b", segments_json=[])
        claim_a = Claim(
            call=call_a,
            data_json={"plaque": "AA 111 AA"},
            status=ClaimStatus.pending_validation,
        )
        claim_b = Claim(
            call=call_b,
            data_json={"plaque": "BB 222 BB"},
            status=ClaimStatus.pending_validation,
        )
        db.add_all([agent_a, agent_b, manager, claim_a, claim_b])
        db.commit()
        data = SecurityData(agent_a, agent_b, manager, claim_a, claim_b, call_a, call_b)

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, factory, data
    app.dependency_overrides.clear()


def authorization(user: User, claimed_role: str | None = None) -> dict[str, str]:
    settings = get_settings()
    token = create_token(user.id, claimed_role or user.role.value, settings)
    return {"Authorization": f"Bearer {token}"}


def test_login_success_failure_and_audit(security_client):
    client, factory, data = security_client

    invalid = client.post(
        "/api/auth/token", data={"username": data.agent_a.username, "password": "wrong"}
    )
    assert invalid.status_code == 401
    assert invalid.headers["www-authenticate"] == "Bearer"

    valid = client.post(
        "/api/auth/token",
        data={"username": data.agent_a.username, "password": "AgentA-secret"},
    )
    assert valid.status_code == 200
    assert valid.json()["token_type"] == "bearer"
    assert valid.json()["username"] == data.agent_a.username
    assert valid.json()["role"] == "agent"

    with factory() as db:
        logins = db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == data.agent_a.id,
                AuditLog.action == "login_success",
            )
        )
    assert logins == 1


def test_missing_and_invalid_tokens_are_rejected(security_client):
    client, _, _ = security_client

    missing = client.get("/api/claims")
    invalid = client.get("/api/claims", headers={"Authorization": "Bearer invalid"})

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401


def test_agent_lists_only_owned_claims(security_client):
    client, _, data = security_client

    response = client.get("/api/claims", headers=authorization(data.agent_a))

    assert response.status_code == 200
    assert [claim["id"] for claim in response.json()] == [data.claim_a.id]


@pytest.mark.parametrize(
    ("method", "path_template", "kwargs"),
    [
        ("put", "/api/claims/{claim_id}", {"json": {"data": {"plaque": "XX 999 XX"}}}),
        ("post", "/api/claims/{claim_id}/validate", {}),
        ("post", "/api/claims/{claim_id}/send", {}),
        ("get", "/api/claims/{claim_id}/export-json", {}),
    ],
)
def test_agent_cannot_act_on_another_agents_claim(
    security_client, method, path_template, kwargs
):
    client, _, data = security_client

    response = getattr(client, method)(
        path_template.format(claim_id=data.claim_b.id),
        headers=authorization(data.agent_a),
        **kwargs,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Déclaration introuvable"


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/calls/{call_id}/extract", {"transcript": "Un véhicule."}),
        ("/api/calls/{call_id}/transcribe", None),
        ("/api/calls/{call_id}/process", None),
    ],
)
def test_agent_cannot_process_another_agents_call(security_client, path, params):
    client, _, data = security_client

    response = client.post(
        path.format(call_id=data.call_b.id),
        params=params,
        headers=authorization(data.agent_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Appel introuvable"


def test_agent_can_update_and_validate_owned_claim(security_client):
    client, factory, data = security_client
    headers = authorization(data.agent_a)

    update = client.put(
        f"/api/claims/{data.claim_a.id}",
        headers=headers,
        json={"data": {"plaque": "AC 1234 CI"}},
    )
    validation = client.post(f"/api/claims/{data.claim_a.id}/validate", headers=headers)

    assert update.status_code == 200
    assert validation.status_code == 200
    with factory() as db:
        saved = db.get(Claim, data.claim_a.id)
        assert saved is not None
        assert saved.data_json["plaque"] == "AC 1234 CI"
        assert saved.human_corrections == 1
        assert saved.validated_by == data.agent_a.id


def test_claim_review_preserves_ai_proposal_and_locks_after_validation(security_client):
    client, _, data = security_client
    headers = authorization(data.agent_a)

    update = client.put(
        f"/api/claims/{data.claim_a.id}",
        headers=headers,
        json={"data": {"plaque": "AC 1234 CI"}},
    )
    review = client.get(f"/api/claims/{data.claim_a.id}", headers=headers)
    validation = client.post(f"/api/claims/{data.claim_a.id}/validate", headers=headers)
    locked = client.put(
        f"/api/claims/{data.claim_a.id}",
        headers=headers,
        json={"data": {"plaque": "AB 0000 CI"}},
    )

    assert update.status_code == 200
    assert review.status_code == 200
    assert review.json()["proposed_data"]["plaque"] == "AA 111 AA"
    assert review.json()["current_data"]["plaque"] == "AC 1234 CI"
    assert validation.status_code == 200
    assert locked.status_code == 409


def test_json_export_requires_validation_at_api_boundary(security_client):
    client, _, data = security_client
    headers = authorization(data.agent_a)

    rejected = client.get(
        f"/api/claims/{data.claim_a.id}/export-json", headers=headers
    )
    client.post(f"/api/claims/{data.claim_a.id}/validate", headers=headers)
    exported = client.get(
        f"/api/claims/{data.claim_a.id}/export-json", headers=headers
    )

    assert rejected.status_code == 409
    assert exported.status_code == 200
    assert exported.json()["path"].endswith(".json")


def test_validated_claim_export_send_and_replay_are_audited(
    security_client, monkeypatch
):
    client, factory, data = security_client
    headers = authorization(data.agent_a)

    async def fake_create(_self, claim_id, _data, human_validated, *, correlation_id):
        assert human_validated is True
        assert correlation_id
        return {"id": f"EXT-{claim_id}", "statut": "recu"}

    monkeypatch.setattr(
        "econstat.api.routes.EConstaClient.create_claim", fake_create
    )
    validation = client.post(f"/api/claims/{data.claim_a.id}/validate", headers=headers)
    exported = client.get(
        f"/api/claims/{data.claim_a.id}/export-json", headers=headers
    )
    sent = client.post(f"/api/claims/{data.claim_a.id}/send", headers=headers)
    replay = client.post(f"/api/claims/{data.claim_a.id}/send", headers=headers)

    assert validation.status_code == 200
    assert exported.status_code == 200
    assert sent.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["id"] == sent.json()["id"]
    with factory() as db:
        actions = db.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == data.claim_a.id)
        ).all()
    assert "json_export_generated" in actions
    assert "econsta_send_attempted" in actions
    assert "sent_to_econsta" in actions
    assert "econsta_idempotent_replay" in actions


def test_econsta_failure_is_visible_and_audited(security_client, monkeypatch):
    from econstat.services.econsta import EConstaTimeoutError

    client, factory, data = security_client
    headers = authorization(data.agent_a)

    async def fail(*_args, **_kwargs):
        raise EConstaTimeoutError("Le service E-consta n’a pas répondu à temps.")

    monkeypatch.setattr("econstat.api.routes.EConstaClient.create_claim", fail)
    client.post(f"/api/claims/{data.claim_a.id}/validate", headers=headers)
    response = client.post(f"/api/claims/{data.claim_a.id}/send", headers=headers)

    assert response.status_code == 504
    with factory() as db:
        actions = db.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == data.claim_a.id)
        ).all()
    assert "econsta_send_attempted" in actions
    assert "econsta_send_failed" in actions


def test_database_role_wins_over_forged_token_role(security_client):
    client, _, data = security_client

    response = client.get(
        "/api/dashboard", headers=authorization(data.agent_a, claimed_role="responsable")
    )

    assert response.status_code == 403


def test_manager_can_list_all_claims_and_open_dashboard(security_client):
    client, _, data = security_client
    headers = authorization(data.manager)

    claims = client.get("/api/claims", headers=headers)
    dashboard = client.get("/api/dashboard", headers=headers)

    assert claims.status_code == 200
    assert {claim["id"] for claim in claims.json()} == {data.claim_a.id, data.claim_b.id}
    assert dashboard.status_code == 200
    assert dashboard.json()["declarations"] == 2
