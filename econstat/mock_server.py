import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="E-consta Mock", version="1.0.0")
store: dict[str, dict] = {}


class Sinistre(BaseModel):
    reference_locale: str
    declaration: dict
    validation_humaine: bool


@app.post("/sinistres", status_code=201)
def create_sinistre(body: Sinistre):
    if not body.validation_humaine:
        raise HTTPException(422, "validation_humaine doit être vraie")
    external_id = f"ECI-{uuid.uuid4().hex[:10].upper()}"
    store[external_id] = {"id": external_id, "statut": "recu", **body.model_dump()}
    return store[external_id]


@app.get("/sinistres/{external_id}")
def get_sinistre(external_id: str):
    if external_id not in store:
        raise HTTPException(404, "Sinistre inconnu")
    return store[external_id]
