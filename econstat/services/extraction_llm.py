"""Complément Ollama strict : aucune proposition sans preuve littérale."""

import json
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from econstat.config import Settings
from econstat.schemas.claim import ClaimData
from econstat.services.model_selector import select_qwen_model

FIELD_TYPES = {
    "nom_assure": "string",
    "telephone_assure": "string",
    "assureur": "string",
    "lieu": "string",
    "date_accident": "YYYY-MM-DD",
    "heure_accident": "HH:MM:SS",
    "type_accident": "string",
    "nombre_vehicules": "integer 1..20",
    "dommages": "string",
    "zone_endommagee": "string",
    "vehicule_immobilise": "boolean",
    "plaque": "string",
    "besoin_assistance": "boolean",
    "tiers_impliques": "boolean",
    "circonstances": "string",
    "blesses": "boolean",
    "informations_complementaires": "string",
}


class LLMFieldProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: object | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1)


class LLMStrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, LLMFieldProposal]


@dataclass
class LLMExtractionOutcome:
    fields: dict[str, LLMFieldProposal] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)
    status: str = "not_run"
    trace: dict = field(default_factory=dict)


def literal_evidence_exists(transcript: str, evidence: str) -> bool:
    return bool(evidence.strip()) and evidence.casefold() in transcript.casefold()


class OllamaExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def extract(self, transcript: str) -> LLMExtractionOutcome:
        if not self.settings.ollama_enabled or not self.settings.enable_llm:
            return LLMExtractionOutcome(status="disabled", trace={"llm": "disabled"})
        selected = select_qwen_model(self.settings)
        prompt = (
            "/no_think\n"
            "Tu extrais seulement les faits explicitement présents dans TRANSCRIPT. "
            "Réponds uniquement avec un JSON strict de forme "
            '{"fields":{"nom_du_champ":{"value":...,"confidence":0.0,'
            '"evidence":"extrait littéral exact"}}}. '
            "Omettre les champs absents. N’ajoute aucun champ sans extrait exact. "
            f"Champs autorisés et types: {json.dumps(FIELD_TYPES, ensure_ascii=False)}\n"
            f"TRANSCRIPT:\n{transcript}"
        )
        payload = {
            "model": selected.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.settings.llm_temperature,
                "seed": self.settings.llm_seed,
                "num_predict": 800,
            },
        }
        trace = {
            "model": selected.model,
            "device": selected.device,
            "temperature": self.settings.llm_temperature,
            "seed": self.settings.llm_seed,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/generate", json=payload
                )
                response.raise_for_status()
            raw = json.loads(response.json()["response"])
            parsed = LLMStrictResponse.model_validate(raw)
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            return LLMExtractionOutcome(
                status="unavailable",
                trace={**trace, "error_type": type(exc).__name__},
            )

        accepted: dict[str, LLMFieldProposal] = {}
        rejected: dict[str, str] = {}
        for name, proposal in parsed.fields.items():
            if name not in ClaimData.model_fields:
                rejected[name] = "unknown_field"
            elif proposal.value is None:
                rejected[name] = "null_value"
            elif not literal_evidence_exists(transcript, proposal.evidence):
                rejected[name] = "evidence_not_literal"
            else:
                accepted[name] = proposal
        return LLMExtractionOutcome(
            fields=accepted,
            rejected=rejected,
            status="completed",
            trace={**trace, "accepted": len(accepted), "rejected": len(rejected)},
        )
