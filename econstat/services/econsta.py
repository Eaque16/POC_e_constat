import uuid

import httpx

from econstat.config import Settings


class EConstaError(RuntimeError):
    pass


class EConstaTimeoutError(EConstaError):
    pass


class EConstaClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = settings.econsta_base_url.rstrip("/")
        self.api_key = settings.econsta_api_key
        self.timeout = settings.econsta_timeout_seconds
        self.transport = transport

    def _headers(self, correlation_id: str, idempotency_key: str | None = None) -> dict:
        headers = {"X-API-Key": self.api_key, "X-Correlation-ID": correlation_id}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def create_claim(
        self,
        claim_id: str,
        data: dict,
        human_validated: bool,
        *,
        correlation_id: str | None = None,
    ) -> dict:
        if not human_validated:
            raise PermissionError("Validation humaine explicite obligatoire avant tout envoi")
        correlation_id = correlation_id or str(uuid.uuid4())
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.post(
                    f"{self.base_url}/sinistres",
                    json={
                        "reference_locale": claim_id,
                        "declaration": data,
                        "validation_humaine": True,
                    },
                    headers=self._headers(correlation_id, claim_id),
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise EConstaTimeoutError("Le service E-consta n’a pas répondu à temps.") from exc
        except httpx.HTTPError as exc:
            raise EConstaError(f"Échec de communication avec E-consta : {exc}") from exc
        result = response.json()
        result.setdefault("correlation_id", correlation_id)
        return result

    async def get_claim(self, external_id: str, *, correlation_id: str | None = None) -> dict:
        correlation_id = correlation_id or str(uuid.uuid4())
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"{self.base_url}/sinistres/{external_id}",
                    headers=self._headers(correlation_id),
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise EConstaTimeoutError("Le service E-consta n’a pas répondu à temps.") from exc
        except httpx.HTTPError as exc:
            raise EConstaError(f"Échec de communication avec E-consta : {exc}") from exc
        return response.json()
