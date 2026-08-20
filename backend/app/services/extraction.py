"""Conservative extraction of explicit claim information from French text."""

import re
import unicodedata
from datetime import date, timedelta

from backend.app.schemas.claim import Assure, EConstat, Sinistre, Vehicule


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip(" .,:;-").split())
    return cleaned or None


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> str | None:
    match = re.search(pattern, text, flags)
    return _clean(match.group(1)) if match else None


def _parse_date(text: str) -> date | None:
    lowered = text.lower()
    if re.search(r"\baujourd['’]hui\b", lowered):
        return date.today()
    if re.search(r"\bhier\b", lowered):
        return date.today() - timedelta(days=1)

    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def _extract_damages(text: str) -> list[str]:
    vocabulary = {
        "aile": "aile",
        "capot": "capot",
        "pare-chocs": "pare-chocs",
        "pare choc": "pare-chocs",
        "phare": "phare",
        "portiere": "portiere",
        "porte": "porte",
        "retroviseur": "retroviseur",
        "vitre": "vitre",
    }
    normalized = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return sorted({label for term, label in vocabulary.items() if term in normalized})


def extract_claim(transcription: str) -> EConstat:
    """Extract only explicit information; unknown values remain null."""

    full_name = _search(
        r"(?:je m['’]appelle|mon nom est)\s+([A-Za-zÀ-ÖØ-öø-ÿ'’-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'’-]+){0,2})",
        transcription,
    )
    if full_name:
        full_name = re.split(r"\s+(?:et|j['’]ai|jai|j’ai)\b", full_name, maxsplit=1, flags=re.IGNORECASE)[0]
    name_parts = full_name.split(maxsplit=1) if full_name else []
    first_name = name_parts[0] if name_parts else None
    last_name = name_parts[1] if len(name_parts) > 1 else None

    telephone = _search(
        r"(?:telephone|numero)\s*(?:est|:)?\s*((?:\+?\d[ .-]?){8,15})",
        transcription,
    )
    contract = _search(
        r"(?:contrat|police)\s*(?:numero|n[°o])?\s*(?:est|:)?\s*([A-Z0-9-]{4,})",
        transcription,
    )
    registration = _search(
        r"(?:immatriculation|plaque)\s*(?:est|:)?\s*([A-Z0-9 -]{4,15})",
        transcription,
    )
    location = _search(
        r"(?:a eu lieu|accident(?:\s+s['’]est produit)?|c['’]etait|c['’]était)\s+(?:a|à)\s+([A-Za-zÀ-ÖØ-öø-ÿ'’-]+)",
        transcription,
    )
    if location is None:
        location = _search(
            r"(?:heure(?:s)?|h\s*\d{0,2})\s+(?:a|à)\s+([A-Za-zÀ-ÖØ-öø-ÿ'’-]+)",
            transcription,
        )
    if location is None:
        location = _search(
            r"(?:aujourd['’]hui|hier|ce matin|cet apres-midi|cet après-midi|ce soir)"
            r"\s+(?:a|à)\s+([A-Za-zÀ-ÖØ-öø-ÿ'’-]+)",
            transcription,
        )
    hour = _search(r"\b(?:vers|a|à)\s+(\d{1,2}(?:\s*h(?:eures?)?\s*\d{0,2})?)", transcription)
    parsed_hour = None
    if hour:
        numbers = re.findall(r"\d+", hour)
        try:
            parsed_hour = f"{int(numbers[0]):02d}:{int(numbers[1]) if len(numbers) > 1 else 0:02d}"
        except (IndexError, ValueError):
            parsed_hour = None

    lowered = transcription.lower()
    claim_type = None
    if any(word in lowered for word in ("percut", "collision", "accroch")):
        claim_type = "collision"
    elif "vol" in lowered:
        claim_type = "vol"
    elif any(word in lowered for word in ("incendie", "brule", "brûle")):
        claim_type = "incendie"

    return EConstat(
        assure=Assure(
            nom=last_name,
            prenom=first_name,
            telephone=telephone,
            numero_contrat=contract,
        ),
        vehicule=Vehicule(immatriculation=registration),
        sinistre=Sinistre(
            type_sinistre=claim_type,
            date_sinistre=_parse_date(transcription),
            heure_sinistre=parsed_hour,
            lieu=location,
            description=transcription,
            degats=_extract_damages(transcription),
        ),
        transcription=transcription,
    )
