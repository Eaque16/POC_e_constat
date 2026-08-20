"""Domain vocabulary and cautious suggestions for Ivorian entities."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from backend.app.schemas.extraction import CorrectionSuggestion

REFERENCE_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "reference"


def normalize_token(value: str) -> str:
    """Normalize accents and punctuation for comparison, not for display."""

    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_value.lower())


@lru_cache(maxsize=None)
def load_lexicon(filename: str) -> tuple[str, ...]:
    path = REFERENCE_DIRECTORY / filename
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def whisper_domain_prompt() -> str:
    """Return short vocabulary hints that improve local proper-noun decoding."""

    places = ", ".join(load_lexicon("ivory_coast_places.txt"))
    names = ", ".join(load_lexicon("ivorian_names.txt"))
    return f"Déclaration de sinistre automobile en Côte d'Ivoire. Lieux : {places}. Noms possibles : {names}."


def _nearest(value: str, candidates: tuple[str, ...], threshold: float) -> tuple[str, float] | None:
    normalized_value = normalize_token(value)
    if not normalized_value:
        return None
    scored = [
        (candidate, SequenceMatcher(None, normalized_value, normalize_token(candidate)).ratio())
        for candidate in candidates
    ]
    candidate, score = max(scored, key=lambda item: item[1])
    if score < threshold or normalize_token(candidate) == normalized_value:
        return None
    return candidate, score


def find_correction_suggestions(claim: object) -> list[CorrectionSuggestion]:
    """Suggest likely spellings without modifying critical extracted values."""

    suggestions: list[CorrectionSuggestion] = []
    location = getattr(getattr(claim, "sinistre", None), "lieu", None)
    if location and (match := _nearest(location, load_lexicon("ivory_coast_places.txt"), 0.74)):
        suggested, confidence = match
        suggestions.append(
            CorrectionSuggestion(
                field="sinistre.lieu",
                heard=location,
                suggested=suggested,
                confidence=round(confidence, 3),
                confirmation_question=f"Le lieu est-il bien {suggested} ?",
            )
        )

    insured = getattr(claim, "assure", None)
    for attribute in ("prenom", "nom"):
        value = getattr(insured, attribute, None)
        if value and (match := _nearest(value, load_lexicon("ivorian_names.txt"), 0.82)):
            suggested, confidence = match
            suggestions.append(
                CorrectionSuggestion(
                    field=f"assure.{attribute}",
                    heard=value,
                    suggested=suggested,
                    confidence=round(confidence, 3),
                    confirmation_question=f"Avez-vous dit {suggested} ? Pouvez-vous l'épeler ?",
                )
            )
    return suggestions
