"""Moteur conversationnel déterministe pour la pré-déclaration automobile."""

import re
import unicodedata
from datetime import date, datetime, time

from econstat.config import get_settings
from econstat.schemas.claim import QUESTION_TEMPLATES, ClaimData
from econstat.services.lexicon import LocalLexicon

WELCOME_MESSAGE = (
    "Bonjour, je suis l’assistant de pré-déclaration automobile. "
    "Je vais recueillir les informations utiles concernant votre accident.\n\n"
    "Pouvez-vous me donner votre nom complet ?"
)

FAQ = (
    (
        ("délai", "combien de temps"),
        "Déclarez l’accident le plus tôt possible. À titre indicatif, certains assureurs "
        "en Côte d’Ivoire demandent une déclaration sous 5 jours ; vérifiez votre contrat "
        "ou confirmez ce délai avec votre assureur.",
    ),
    (
        ("document", "pièce", "fournir"),
        "Préparez si possible : attestation d’assurance, carte grise, permis, constat "
        "amiable ou PV, photos des véhicules et dégâts, ainsi que les coordonnées du tiers. "
        "La liste finale dépend de l’assureur et du dossier.",
    ),
    (
        ("constat", "police", "gendarmerie"),
        "S’il n’y a que des dégâts matériels et que la situation le permet, remplissez un "
        "constat amiable lisible avec l’autre conducteur. En cas de blessé, désaccord, "
        "délit de fuite ou danger, sollicitez la police ou la gendarmerie.",
    ),
    (
        ("réparer", "garage"),
        "Évitez d’engager des réparations définitives avant les instructions de l’assureur "
        "ou le passage éventuel d’un expert. Prenez des photos et conservez les justificatifs.",
    ),
    (
        ("photo",),
        "Photographiez la vue générale, les positions si cela peut être fait sans danger, "
        "les plaques, les dégâts, la signalisation et les documents échangés.",
    ),
    (
        ("responsable", "tort"),
        "Je peux recueillir les faits, mais je ne détermine pas la responsabilité. Elle sera "
        "appréciée à partir du constat, des preuves et des règles applicables.",
    ),
)

FLOW = (
    "nom_assure",
    "telephone_assure",
    "assureur",
    "plaque",
    "date_accident",
    "heure_accident",
    "lieu",
    "type_accident",
    "nombre_vehicules",
    "tiers_impliques",
    "circonstances",
    "dommages",
    "zone_endommagee",
    "vehicule_immobilise",
)

MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
DAY_WORDS = {
    "premier": 1,
    "un": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
    "dix sept": 17,
    "dix huit": 18,
    "dix neuf": 19,
    "vingt": 20,
    "vingt et un": 21,
    "vingt deux": 22,
    "vingt trois": 23,
    "vingt quatre": 24,
    "vingt cinq": 25,
    "vingt six": 26,
    "vingt sept": 27,
    "vingt huit": 28,
    "vingt neuf": 29,
    "trente": 30,
    "trente et un": 31,
}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("-", " "))
    return " ".join("".join(c for c in normalized if not unicodedata.combining(c)).split())


def parse_spoken_date(raw: str, today: date | None = None) -> str | None:
    reference = today or date.today()
    plain = _plain(raw)
    if plain in {"aujourd'hui", "aujourd hui", "ce jour"}:
        return reference.isoformat()
    if plain == "hier":
        return date.fromordinal(reference.toordinal() - 1).isoformat()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    match = re.search(rf"(?:le )?(.+?) ({'|'.join(MONTHS)}) (.+)$", plain)
    if not match:
        return None
    day_text, month_text, year_text = match.groups()
    day = int(day_text) if day_text.isdigit() else DAY_WORDS.get(day_text)
    years = {
        "deux mille vingt quatre": 2024,
        "deux mille vingt cinq": 2025,
        "deux mille vingt six": 2026,
        "deux mille vingt sept": 2027,
        "deux mille vingt huit": 2028,
        "deux mille vingt neuf": 2029,
        "deux mille trente": 2030,
    }
    year = int(year_text) if year_text.isdigit() else years.get(year_text)
    try:
        return date(year, MONTHS[month_text], day).isoformat() if day and year else None
    except ValueError:
        return None


def new_conversation() -> dict:
    return {
        "data": {},
        "transcript": [f"ASSISTANT: {WELCOME_MESSAGE}"],
        "current_field": "nom_assure",
    }


def _yes_no(text: str) -> bool | None:
    value = text.lower().strip()
    if re.search(r"\b(non|aucun|aucune|pas de|ne .* pas)\b", value):
        return False
    if re.search(r"\b(oui|un|une|des|besoin|immobilis|bless)\b", value):
        return True
    return None


def _parse(field: str, text: str):
    raw = text.strip()
    if field in {"blesses", "besoin_assistance", "tiers_impliques", "vehicule_immobilise"}:
        return _yes_no(raw)
    if field == "nombre_vehicules":
        words = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4}
        match = re.search(r"\b([1-9]|un|une|deux|trois|quatre)\b", raw.lower())
        if not match:
            return None
        return int(match.group(1)) if match.group(1).isdigit() else words[match.group(1)]
    if field == "date_accident":
        return parse_spoken_date(raw)
    if field == "heure_accident":
        match = re.search(r"\b([01]?\d|2[0-3])(?:\s*h|:)([0-5]\d)?\b", raw.lower())
        return time(int(match.group(1)), int(match.group(2) or 0)).isoformat() if match else None
    if field == "plaque":
        return " ".join(raw.upper().split()) if len(raw) >= 4 else None
    if field == "telephone_assure":
        digits = re.sub(r"\D", "", raw)
        return digits if 8 <= len(digits) <= 13 else None
    lexicon = LocalLexicon(get_settings().lexicon_path)
    if field == "lieu":
        return lexicon.correct(raw, "lieux")
    if field == "assureur":
        return lexicon.correct(raw, "assureurs")
    if field == "nom_assure":
        parts = [lexicon.correct(part, "noms_ivoiriens", 86) for part in raw.split()]
        return " ".join(parts).title()
    return raw if len(raw) >= 2 else None


def _faq_answer(text: str) -> str | None:
    lowered = text.lower()
    if not ("?" in text or re.match(r"^(comment|que|quel|dois|est-ce|combien)", lowered)):
        return None
    for keywords, answer in FAQ:
        if any(keyword in lowered for keyword in keywords):
            return answer
    return None


def _next_field(data: dict) -> str | None:
    return next((field for field in FLOW if data.get(field) is None), None)


def progress(data: dict) -> int:
    return round(100 * sum(data.get(field) is not None for field in FLOW) / len(FLOW))


def respond(message: str, state: dict | None) -> tuple[str, dict]:
    state = state or new_conversation()
    data = dict(state.get("data", {}))
    transcript = list(state.get("transcript", []))
    transcript.append(f"CLIENT: {message.strip()}")
    field = state.get("current_field") or _next_field(data)
    if faq := _faq_answer(message):
        reply = (
            f"{faq}\n\nReprenons la pré-déclaration : {QUESTION_TEMPLATES[field]}" if field else faq
        )
    elif not field:
        reply = "La pré-déclaration est complète. Vérifiez le récapitulatif puis créez le dossier."
    else:
        value = _parse(field, message)
        if value is None:
            reply = f"Je n’ai pas pu confirmer cette information. {QUESTION_TEMPLATES[field]}"
        else:
            data[field] = value
            field = _next_field(data)
            if field:
                reply = f"Merci, c’est noté.\n\n{QUESTION_TEMPLATES[field]}"
            else:
                reply = (
                    "Merci. Les informations essentielles sont recueillies. Vérifiez le "
                    "récapitulatif avant de créer le dossier ; un agent humain devra encore "
                    "le contrôler."
                )
    transcript.append(f"ASSISTANT: {reply}")
    return reply, {
        **state,
        "data": data,
        "transcript": transcript,
        "current_field": field,
    }


def summary_markdown(state: dict | None) -> str:
    data = (state or {}).get("data", {})
    if not data:
        return "**Avancement : 0 %** — aucune information confirmée."
    rows = "\n".join(
        f"- **{key.replace('_', ' ').capitalize()}** : {value}" for key, value in data.items()
    )
    return f"**Avancement : {progress(data)} %**\n\n{rows}"


def validated_data(state: dict) -> ClaimData:
    return ClaimData.model_validate(state.get("data", {}))
