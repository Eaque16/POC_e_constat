"""Extraction déterministe avec preuve littérale pour chaque champ proposé."""

import re
from dataclasses import dataclass, field
from datetime import date

from econstat.services.lexicon import LocalLexicon

NUMBERS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4}


@dataclass
class RuleExtraction:
    data: dict = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)
    rules: dict[str, str] = field(default_factory=dict)

    def add(self, name: str, value, confidence: float, evidence: str, rule: str) -> None:
        if name not in self.data and evidence:
            self.data[name] = value
            self.confidence[name] = confidence
            self.evidence[name] = evidence
            self.rules[name] = rule


def _first(pattern: str, transcript: str, flags: int = re.I):
    return re.search(pattern, transcript, flags)


def extract_rules(transcript: str, lexicon: LocalLexicon) -> RuleExtraction:
    result = RuleExtraction()

    match = _first(
        r"\b(?:plaque|immatriculation)\s*(?:est|c'est|:)?\s*"
        r"([A-Z]{1,3}[ -]?\d{2,4}[ -]?[A-Z]{1,3})\b",
        transcript,
    )
    if match:
        result.add("plaque", match.group(1), 0.94, match.group(0), "plaque_explicit")

    match = _first(r"\b(?:\+225[ .-]?)?(0[157](?:[ .-]?\d{2}){4})\b", transcript)
    if match:
        result.add(
            "telephone_assure",
            re.sub(r"[ .-]", "", match.group(1)),
            0.94,
            match.group(0),
            "telephone_ci",
        )

    match = _first(r"\b(un|une|deux|trois|quatre|[1-9])\s+véhicules?\b", transcript)
    if match:
        raw = match.group(1).lower()
        value = NUMBERS.get(raw, int(raw) if raw.isdigit() else None)
        result.add("nombre_vehicules", value, 0.93, match.group(0), "vehicle_count")

    match = _first(r"\b([01]?\d|2[0-3])(?:\s*h(?:eures?)?|:)([0-5]\d)?\b", transcript)
    if match:
        value = f"{int(match.group(1)):02d}:{int(match.group(2) or 0):02d}:00"
        result.add("heure_accident", value, 0.92, match.group(0), "time_24h")

    match = _first(r"\b(0?[1-9]|[12]\d|3[01])[/-](0?[1-9]|1[0-2])[/-](20\d{2})\b", transcript)
    if match:
        try:
            value = date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
            result.add("date_accident", value, 0.94, match.group(0), "date_dmy")
        except ValueError:
            pass

    match = _first(r"\b(?:je suis|mon nom est)\s+([A-ZÀ-Ÿ][\wÀ-ÿ' -]{2,50})", transcript)
    if match:
        name = re.split(r"[.,;\n]", match.group(1))[0].strip()
        result.add("nom_assure", name, 0.88, match.group(0), "self_identification")

    for category, field_name, confidence in (
        ("lieux", "lieu", 0.9),
        ("assureurs", "assureur", 0.9),
    ):
        if found := lexicon.literal_match(transcript, category):
            result.add(field_name, found[0], confidence, found[1], f"lexicon_{category}")

    if found := lexicon.accident_match(transcript):
        result.add("type_accident", found[0], 0.88, found[1], "lexicon_accident")

    binary_rules = (
        ("vehicule_immobilise", True, r"\b(ne roule plus|immobilisé|ne démarre plus)\b", 0.92),
        ("vehicule_immobilise", False, r"\b(peut rouler|roule encore)\b", 0.9),
        ("besoin_assistance", False, r"\b(pas besoin d'assistance|sans assistance)\b", 0.9),
        (
            "besoin_assistance",
            True,
            r"\b(remorquage|dépanneuse|besoin d'assistance|assistance)\b",
            0.9,
        ),
        ("tiers_impliques", True, r"\b(un tiers|autre véhicule|deux véhicules)\b", 0.86),
        ("tiers_impliques", False, r"\b(aucun tiers|seul véhicule)\b", 0.9),
        ("blesses", True, r"\b(un blessé|des blessés|personne blessée)\b", 0.94),
        ("blesses", False, r"\b(pas de blessé|aucun blessé)\b", 0.94),
    )
    for field_name, value, pattern, confidence in binary_rules:
        if match := _first(pattern, transcript):
            result.add(field_name, value, confidence, match.group(0), f"binary_{field_name}")

    if match := _first(r"\b(pare-chocs[^.\n]{0,80}|coffre[^.\n]{0,80})", transcript):
        result.add("dommages", match.group(0).strip(), 0.86, match.group(0), "damage_phrase")
    if match := _first(r"\b(arrière|avant|côté gauche|côté droit) du véhicule\b", transcript):
        result.add("zone_endommagee", match.group(0), 0.88, match.group(0), "damage_zone")
    if match := _first(r"[^.\n]*(?:percut|collision|accident)[^.\n]*[.]?", transcript):
        phrase = match.group(0).strip()
        result.add("circonstances", phrase, 0.78, phrase, "accident_sentence")
    return result


def deterministic_extract(transcript: str, lexicon: LocalLexicon) -> tuple[dict, dict]:
    result = extract_rules(transcript, lexicon)
    return result.data, result.confidence
