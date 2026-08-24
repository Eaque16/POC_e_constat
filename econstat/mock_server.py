import uuid

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

app = FastAPI(title="E-consta Mock", version="1.1.0")
store: dict[str, dict] = {}
reference_index: dict[str, str] = {}


class Sinistre(BaseModel):
    reference_locale: str
    declaration: dict
    validation_humaine: bool


@app.post("/sinistres", status_code=201)
def create_sinistre(
    body: Sinistre,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    if not body.validation_humaine:
        raise HTTPException(422, "validation_humaine doit être vraie")
    key = idempotency_key or body.reference_locale
    if key in reference_index:
        existing = store[reference_index[key]]
        same_payload = (
            existing["reference_locale"] == body.reference_locale
            and existing["declaration"] == body.declaration
        )
        if not same_payload:
            raise HTTPException(409, "Clé d’idempotence utilisée avec un contenu différent")
        response.status_code = 200
        return {**existing, "idempotent_replay": True, "correlation_id": correlation_id}
    external_id = f"ECI-{uuid.uuid4().hex[:10].upper()}"
    stored = {"id": external_id, "statut": "recu", **body.model_dump()}
    store[external_id] = stored
    reference_index[key] = external_id
    return {**stored, "idempotent_replay": False, "correlation_id": correlation_id}


@app.get("/sinistres/{external_id}")
def get_sinistre(external_id: str):
    if external_id not in store:
        raise HTTPException(404, "Sinistre inconnu")
    return store[external_id]
