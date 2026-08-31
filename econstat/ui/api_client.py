from pathlib import Path
from typing import Any

import httpx


class APIError(RuntimeError):
    pass


class EConstatAPI:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def _request(self, method: str, path: str, token: str | None = None, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if token:
            headers["Authorization"] = f"Bearer {token}"
        timeout = kwargs.pop("timeout", 30)
        try:
            with httpx.Client(
                base_url=self.base_url, timeout=timeout, transport=self.transport
            ) as client:
                response = client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except ValueError:
                detail = exc.response.text
            raise APIError(str(detail)) from exc
        except httpx.HTTPError as exc:
            raise APIError(f"API locale indisponible : {exc}") from exc
        return response.json() if response.content else None

    def login(self, username: str, password: str) -> dict:
        return self._request(
            "POST", "/auth/token", data={"username": username, "password": password}
        )

    def upload(self, token: str, audio_path: str, profile: str) -> dict:
        path = Path(audio_path)
        with path.open("rb") as stream:
            return self._request(
                "POST",
                "/calls",
                token,
                files={"audio": (path.name, stream, "application/octet-stream")},
                data={"profile": profile},
                timeout=120,
            )

    def jobs(self, token: str) -> list[dict]:
        return self._request("GET", "/jobs", token)

    def retry_job(self, token: str, job_id: str) -> dict:
        return self._request("POST", f"/jobs/{job_id}/retry", token)

    def claims(self, token: str) -> list[dict]:
        return self._request("GET", "/claims", token)

    def claim(self, token: str, claim_id: str) -> dict:
        return self._request("GET", f"/claims/{claim_id}", token)

    def call(self, token: str, call_id: str) -> dict:
        return self._request("GET", f"/calls/{call_id}", token)

    def update_claim(self, token: str, claim_id: str, data: dict) -> dict:
        return self._request("PUT", f"/claims/{claim_id}", token, json={"data": data})

    def correct_speakers(self, token: str, call_id: str, corrections: list[dict]) -> dict:
        return self._request(
            "PUT",
            f"/calls/{call_id}/speakers",
            token,
            json={"corrections": corrections},
        )

    def validate(self, token: str, claim_id: str) -> dict:
        return self._request("POST", f"/claims/{claim_id}/validate", token)

    def export_json(self, token: str, claim_id: str) -> dict:
        return self._request("GET", f"/claims/{claim_id}/export-json", token)

    def send(self, token: str, claim_id: str) -> dict:
        return self._request("POST", f"/claims/{claim_id}/send", token)

    def dashboard(self, token: str) -> dict:
        return self._request("GET", "/dashboard", token)

    def create_conversation_claim(
        self,
        token: str,
        data: dict,
        transcript: list[str],
        claim_id: str | None = None,
        field_records: dict[str, dict] | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/conversations/claims",
            token,
            json={
                "data": data,
                "transcript": transcript,
                "claim_id": claim_id,
                "field_records": field_records or {},
            },
        )
