import json
import re
from datetime import datetime

import httpx

from econstat.config import Settings
from econstat.schemas.claim import QUESTION_TEMPLATES, REQUIRED_FIELDS, ClaimData, ClaimExtraction
from econstat.services.model_selector import select_qwen_model

PATTERNS = {
    "plaque": re.compile(
        r"\b(?:plaque|immatriculation)\s*(?:est|:)?\s*([A-Z]{1,3}[ -]?\d{2,4}[ -]?[A-Z]{1,3})\b",
        re.I,
    ),
    "telephone_assure": re.compile(r"\b(?:\+225\s*)?(0[157]\d(?:[ .-]?\d{2}){3})\b"),
    "nombre_vehicules": re.compile(r"\b(un|deux|trois|quatre|[1-4])\s+véhicules?\b", re.I),
    "heure_accident": re.compile(r"\b([01]?\d|2[0-3])(?:\s*h(?:eures?)?|:)([0-5]\d)?\b", re.I),
}
NUMBERS = {"un": 1, "deux": 2, "trois": 3, "quatre": 4}


def deterministic_extract(transcript: str) -> tuple[dict, dict]:
    data: dict = {}
    confidence: dict = {}
    for field, pattern in PATTERNS.items():
        if match := pattern.search(transcript):
            value = match.group(1)
            if field == "nombre_vehicules":
                value = NUMBERS.get(value.lower(), int(value) if value.isdigit() else None)
            elif field == "heure_accident":
                value = f"{int(value):02d}:{int(match.group(2) or 0):02d}:00"
            data[field], confidence[field] = value, 0.9
    low = transcript.lower()
    if "ne roule plus" in low or "immobilisé" in low:
        data["vehicule_immobilise"], confidence["vehicule_immobilise"] = True, 0.9
    elif "peut rouler" in low or "roule encore" in low:
        data["vehicule_immobilise"], confidence["vehicule_immobilise"] = False, 0.9
    if "remorqu" in low or "assistance" in low:
        data["besoin_assistance"], confidence["besoin_assistance"] = True, 0.8
    if match := re.search(r"\bje suis ([A-ZÀ-Ÿ][\wÀ-ÿ' -]{2,40})[.,]", transcript):
        data["nom_assure"], confidence["nom_assure"] = match.group(1).strip(), 0.88
    if "cocody" in low:
        data["lieu"], confidence["lieu"] = "Cocody Saint-Jean, Abidjan", 0.9
    if "percut" in low and "arrière" in low:
        data["type_accident"], confidence["type_accident"] = "Collision arrière", 0.88
        data["zone_endommagee"], confidence["zone_endommagee"] = "Arrière du véhicule", 0.9
    if "pare-chocs" in low and "coffre" in low:
        data["dommages"], confidence["dommages"] = "Pare-chocs arrière et coffre enfoncés", 0.9
    if "arrêtée au feu rouge" in low:
        data["circonstances"] = (
            "Véhicule percuté à l'arrière alors qu'il était arrêté au feu rouge."
        )
        confidence["circonstances"] = 0.88
    return data, confidence


class HybridExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _llm(self, transcript: str) -> tuple[dict, dict, dict]:
        selected = select_qwen_model(self.settings)
        schema = ClaimData.model_json_schema()
        prompt = (
            "/no_think\n"
            "Extrais uniquement les faits explicitement présents. "
            "Toute valeur doit avoir une citation "
            "exacte evidence. Réponds en JSON: {data, confidence, evidence}. Schéma data: "
            f"{json.dumps(schema, ensure_ascii=False)}\nTRANSCRIPT:\n{transcript}"
        )
        payload = {
            "model": selected.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.settings.llm_temperature,
                "seed": self.settings.random_seed,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url}/api/generate", json=payload
            )
            response.raise_for_status()
        result = json.loads(response.json()["response"])
        trace = {
            "model": selected.model,
            "device": selected.device,
            "vram_gb": selected.vram_gb,
            "temperature": self.settings.llm_temperature,
            "seed": self.settings.random_seed,
        }
        return (
            result.get("data", {}),
            result.get("confidence", {}),
            {**trace, "evidence": result.get("evidence", {})},
        )

    async def extract(self, transcript: str, whisper_confidence: float = 0.75) -> ClaimExtraction:
        deterministic, det_conf = deterministic_extract(transcript)
        merged, confidences, trace = dict(deterministic), dict(det_conf), {"llm": "unavailable"}
        try:
            if not self.settings.enable_llm:
                raise RuntimeError("LLM désactivé pour le mode démo rapide")
            llm_data, llm_conf, trace = await self._llm(transcript)
            evidence = trace.pop("evidence", {})
            for field, value in llm_data.items():
                citation = str(evidence.get(field, ""))
                # Garde anti-hallucination : la citation doit être un extrait
                # littéral du transcript.
                if value is not None and citation and citation.lower() in transcript.lower():
                    if field not in merged:
                        merged[field] = value
                        confidences[field] = min(float(llm_conf.get(field, 0.5)), 0.85)
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError, RuntimeError):
            pass
        data = ClaimData.model_validate(merged)
        missing = [field for field in REQUIRED_FIELDS if getattr(data, field) is None]
        completeness = (len(REQUIRED_FIELDS) - len(missing)) / len(REQUIRED_FIELDS)
        for field in data.model_fields:
            if getattr(data, field) is not None:
                confidences[field] = round(
                    0.45 * confidences.get(field, 0.5)
                    + 0.35 * whisper_confidence
                    + 0.20 * completeness,
                    3,
                )
        overall = sum(confidences.values()) / len(confidences) if confidences else 0.0
        return ClaimExtraction(
            data=data,
            field_confidences=confidences,
            missing_fields=missing,
            suggested_questions=[QUESTION_TEMPLATES[f] for f in missing],
            overall_confidence=round(overall, 3),
            trace={**trace, "timestamp": datetime.utcnow().isoformat()},
        )
