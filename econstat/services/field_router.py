"""Route un transcript vers le parser du slot attendu, sans extraction générale."""

from __future__ import annotations

from datetime import UTC, datetime

from econstat.services.confidence import composite_confidence
from econstat.services.parsers import (
    parse_date,
    parse_datetime,
    parse_firstname,
    parse_lastname,
    parse_phone,
    parse_plate,
    parse_time,
    parse_yes_no,
)

SLOT_ALIASES = {
    "nom_assure": "lastname",
    "telephone_assure": "phone",
    "plaque": "vehicle_plate",
    "date_accident": "accident_date",
    "heure_accident": "accident_time",
    "lieu": "location",
    "tiers_impliques": "third_party",
    "blesses": "injured",
    "vehicule_immobilise": "yes_no",
}


def parse_expected_field(
    expected_slot: str,
    transcript: str,
    context: dict | None = None,
    *,
    asr_confidence: float = 0.75,
) -> dict:
    context = context or {}
    slot = SLOT_ALIASES.get(expected_slot, expected_slot)
    reference = context.get("call_started_at") or datetime.now(UTC)
    if isinstance(reference, str):
        reference = datetime.fromisoformat(reference)
    spelling = bool(context.get("spelling_mode"))
    precision = "exact"
    metadata: dict = {}

    if slot == "firstname":
        normalized = parse_firstname(transcript, spelling=spelling)
    elif slot == "lastname":
        normalized = parse_lastname(transcript, spelling=spelling)
    elif slot == "phone":
        normalized = parse_phone(transcript)
    elif slot == "vehicle_plate":
        normalized = parse_plate(transcript)
    elif slot == "accident_date":
        temporal = parse_date(transcript, reference)
        normalized, precision = temporal.normalized, temporal.precision
        metadata["warning"] = temporal.warning
    elif slot == "accident_time":
        temporal = parse_time(transcript, reference)
        normalized, precision = temporal.normalized, temporal.precision
    elif slot == "accident_datetime":
        temporal = parse_datetime(transcript, reference)
        normalized, precision = temporal.normalized, temporal.precision
        metadata["warning"] = temporal.warning
    elif slot in {"injured", "third_party", "yes_no"}:
        normalized = parse_yes_no(transcript)
    elif slot == "location":
        resolver = context.get("location_resolver")
        if resolver:
            result = resolver.resolve(
                transcript,
                gps=context.get("gps"),
                asr_confidence=asr_confidence,
            )
            result["whisper_transcript"] = transcript
            result["metadata"] = {
                **result.get("metadata", {}),
                "audio_reference": context.get("audio_reference"),
                "actual_utterance_available_as_audio": bool(context.get("audio_reference")),
            }
            return result
        normalized = transcript.strip() or None
        metadata["verification_status"] = "disabled"
        metadata["verified_in_gazetteer"] = False
    else:
        normalized = transcript.strip() or None

    parser_score = 1.0 if normalized is not None else 0.0
    ambiguity_score = (
        0.55 if precision == "ambiguous" else 0.8 if precision == "approximate" else 1.0
    )
    components = {
        "asr": asr_confidence,
        "parser": parser_score,
        "ambiguity": ambiguity_score,
        "confirmation": 0.0,
    }
    return {
        "slot": slot,
        "raw_transcript": transcript,
        "whisper_transcript": transcript,
        "normalized": normalized,
        "confidence": composite_confidence(
            components, {"asr": 0.35, "parser": 0.4, "ambiguity": 0.25, "confirmation": 0.0}
        ),
        "confidence_components": components,
        "confirmed": False,
        "source": "voice",
        "parser": f"{slot}_parser",
        "evidence": transcript,
        "precision": precision,
        "metadata": {
            **metadata,
            "audio_reference": context.get("audio_reference"),
            "actual_utterance_available_as_audio": bool(context.get("audio_reference")),
        },
    }
