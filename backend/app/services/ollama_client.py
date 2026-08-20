"""Local Ollama client with Pydantic-validated structured output."""

import os
import unicodedata
from datetime import date, time
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, ValidationError

from backend.app.schemas.claim import Assure, EConstat, Sinistre, Vehicule
from backend.app.services.extraction import extract_claim

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:1.5b"
PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "ai" / "prompts" / "claim_extraction_fr.txt"
)


class OllamaExtractionError(RuntimeError):
    """Raised when local structured extraction cannot be completed."""


class ExtractedInsured(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    telephone: str | None = None
    numero_contrat: str | None = None


class ExtractedVehicle(BaseModel):
    immatriculation: str | None = None
    marque: str | None = None
    modele: str | None = None


class ExtractedIncident(BaseModel):
    type_sinistre: str | None = None
    date_sinistre: date | None = None
    heure_sinistre: time | None = None
    lieu: str | None = None
    degats: list[str] = Field(default_factory=list, max_length=10)


class ExtractedClaim(BaseModel):
    """Minimal LLM contract; backend-owned fields are deliberately excluded."""

    assure: ExtractedInsured
    vehicule: ExtractedVehicle
    sinistre: ExtractedIncident


def build_extraction_prompt(transcription: str) -> str:
    """Render the versioned French extraction prompt."""

    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{transcription}", transcription)


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value).lower()
        if character.isalnum()
    )


def _supported_or_fallback(
    proposed: str | None,
    fallback: str | None,
    transcription: str,
) -> str | None:
    """Keep literal critical values only when evidence exists in the source."""

    if proposed and _normalized(proposed) in _normalized(transcription):
        return proposed
    return fallback


def extract_claim_with_ollama(transcription: str) -> EConstat:
    """Extract an E-Constat through Ollama and validate every returned field."""

    ollama_url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    request_body = {
        "model": model,
        "stream": False,
        "format": ExtractedClaim.model_json_schema(),
        "options": {
            "temperature": 0,
            "num_predict": int(os.getenv("OLLAMA_MAX_TOKENS", "256")),
            "num_ctx": int(os.getenv("OLLAMA_CONTEXT_LENGTH", "2048")),
        },
        "messages": [
            {"role": "user", "content": build_extraction_prompt(transcription)}
        ],
    }

    try:
        response = httpx.post(
            f"{ollama_url}/api/chat",
            json=request_body,
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        extracted = ExtractedClaim.model_validate_json(content)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as error:
        raise OllamaExtractionError("Extraction Ollama indisponible ou invalide") from error

    deterministic = extract_claim(transcription)
    safe_type = extracted.sinistre.type_sinistre
    if safe_type not in {"collision", "vol", "incendie"}:
        safe_type = deterministic.sinistre.type_sinistre

    supported_damages = [
        damage
        for damage in extracted.sinistre.degats
        if _normalized(damage) in _normalized(transcription)
    ]
    damages = sorted(set(deterministic.sinistre.degats + supported_damages))

    return EConstat(
        assure=Assure(
            nom=_supported_or_fallback(
                extracted.assure.nom, deterministic.assure.nom, transcription
            ),
            prenom=_supported_or_fallback(
                extracted.assure.prenom, deterministic.assure.prenom, transcription
            ),
            telephone=_supported_or_fallback(
                extracted.assure.telephone,
                deterministic.assure.telephone,
                transcription,
            ),
            numero_contrat=_supported_or_fallback(
                extracted.assure.numero_contrat,
                deterministic.assure.numero_contrat,
                transcription,
            ),
        ),
        vehicule=Vehicule(
            immatriculation=_supported_or_fallback(
                extracted.vehicule.immatriculation,
                deterministic.vehicule.immatriculation,
                transcription,
            ),
            marque=_supported_or_fallback(
                extracted.vehicule.marque,
                deterministic.vehicule.marque,
                transcription,
            ),
            modele=_supported_or_fallback(
                extracted.vehicule.modele,
                deterministic.vehicule.modele,
                transcription,
            ),
        ),
        sinistre=Sinistre(
            type_sinistre=safe_type,
            # Dates and times remain deterministic until explicit evidence
            # checking handles all French relative-date formulations.
            date_sinistre=deterministic.sinistre.date_sinistre,
            heure_sinistre=deterministic.sinistre.heure_sinistre,
            lieu=_supported_or_fallback(
                extracted.sinistre.lieu,
                deterministic.sinistre.lieu,
                transcription,
            ),
            description=transcription,
            degats=damages,
        ),
        transcription=transcription,
    )
