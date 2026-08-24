import httpx
import pytest

from econstat.config import Settings
from econstat.mock_server import app, reference_index, store
from econstat.services.econsta import EConstaClient, EConstaTimeoutError


@pytest.fixture(autouse=True)
def clear_mock_store():
    store.clear()
    reference_index.clear()
    yield
    store.clear()
    reference_index.clear()


@pytest.mark.asyncio
async def test_client_and_mock_are_idempotent_with_correlation():
    transport = httpx.ASGITransport(app=app)
    settings = Settings(econsta_base_url="http://mock", disable_auth=True)
    client = EConstaClient(settings, transport=transport)

    first = await client.create_claim(
        "claim-1", {"plaque": "AB 1234 CI"}, True, correlation_id="corr-1"
    )
    replay = await client.create_claim(
        "claim-1", {"plaque": "AB 1234 CI"}, True, correlation_id="corr-2"
    )

    assert first["id"] == replay["id"]
    assert first["idempotent_replay"] is False
    assert replay["idempotent_replay"] is True
    assert replay["correlation_id"] == "corr-2"
    assert len(store) == 1


@pytest.mark.asyncio
async def test_mock_rejects_reused_key_with_different_content():
    transport = httpx.ASGITransport(app=app)
    headers = {"Idempotency-Key": "claim-1"}
    async with httpx.AsyncClient(base_url="http://mock", transport=transport) as client:
        first = await client.post(
            "/sinistres",
            headers=headers,
            json={
                "reference_locale": "claim-1",
                "declaration": {"plaque": "AB 1234 CI"},
                "validation_humaine": True,
            },
        )
        conflict = await client.post(
            "/sinistres",
            headers=headers,
            json={
                "reference_locale": "claim-1",
                "declaration": {"plaque": "XX 9999 CI"},
                "validation_humaine": True,
            },
        )

    assert first.status_code == 201
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_client_has_independent_human_validation_guard():
    settings = Settings(econsta_base_url="http://mock", disable_auth=True)
    client = EConstaClient(settings, transport=httpx.ASGITransport(app=app))

    with pytest.raises(PermissionError, match="Validation humaine"):
        await client.create_claim("claim-1", {}, False)


@pytest.mark.asyncio
async def test_client_translates_timeout_to_explicit_error():
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    settings = Settings(econsta_base_url="http://mock", disable_auth=True)
    client = EConstaClient(settings, transport=httpx.MockTransport(timeout_handler))

    with pytest.raises(EConstaTimeoutError, match="pas répondu à temps"):
        await client.create_claim("claim-1", {}, True)
