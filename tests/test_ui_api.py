import httpx
import pytest

from econstat.ui.api_client import APIError, EConstatAPI


def test_ui_client_logs_in_and_sends_bearer_token():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "signed-token",
                    "token_type": "bearer",
                    "username": "agent.demo",
                    "role": "agent",
                },
            )
        assert request.headers["authorization"] == "Bearer signed-token"
        return httpx.Response(200, json=[])

    client = EConstatAPI("http://test/api", transport=httpx.MockTransport(handler))
    login = client.login("agent.demo", "secret")

    assert login["role"] == "agent"
    assert client.jobs(login["access_token"]) == []


def test_ui_client_exposes_api_error_without_losing_business_message():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(409, json={"detail": "Validation humaine obligatoire"})
    )
    client = EConstatAPI("http://test/api", transport=transport)

    with pytest.raises(APIError, match="Validation humaine obligatoire"):
        client.send("token", "claim-id")
