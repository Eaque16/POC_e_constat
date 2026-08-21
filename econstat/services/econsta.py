import httpx

from econstat.config import Settings


class EConstaClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.econsta_base_url.rstrip("/")
        self.headers = {"X-API-Key": settings.econsta_api_key}

    async def create_claim(self, claim_id: str, data: dict, human_validated: bool) -> dict:
        if not human_validated:
            raise PermissionError("Validation humaine explicite obligatoire avant tout envoi")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.base_url}/sinistres",
                json={
                    "reference_locale": claim_id,
                    "declaration": data,
                    "validation_humaine": True,
                },
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_claim(self, external_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self.base_url}/sinistres/{external_id}", headers=self.headers
            )
            response.raise_for_status()
            return response.json()
