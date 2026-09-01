"""Moteur conversationnel déterministe pour la pré-déclaration automobile."""

import re
import unicodedata
from datetime import UTC, date, datetime, time

from econstat.config import get_settings
from econstat.schemas.claim import QUESTION_TEMPLATES, ClaimData
from econstat.services.confirmation import needs_confirmation
from econstat.services.field_router import parse_expected_field
from econstat.services.lexicon import LocalLexicon
from econstat.services.location import LocationResolver
from econstat.services.parsers.yes_no_parser import parse_yes_no

WELCOME_MESSAGE = (
    "Bonjour, je suis l’assistant de pré-déclaration automobile. "
    "Je vais recueillir les informations utiles concernant votre accident.\n\n"
    "Quel est votre nom de famille ?"
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
    "lastname",
    "firstname",
    "phone",
    "assureur",
    "vehicle_plate",
    "accident_date",
    "accident_time",
    "location",
    "type_accident",
    "nombre_vehicules",
    "blesses",
    "tiers_impliques",
    "circonstances",
    "dommages",
    "zone_endommagee",
    "vehicule_immobilise",
    "besoin_assistance",
)

SLOT_QUESTIONS = {
    "lastname": "Quel est votre nom de famille ?",
    "firstname": "Quel est votre prénom ?",
    "phone": QUESTION_TEMPLATES["telephone_assure"],
    "vehicle_plate": QUESTION_TEMPLATES["plaque"],
    "accident_date": QUESTION_TEMPLATES["date_accident"],
    "accident_time": QUESTION_TEMPLATES["heure_accident"],
    "location": QUESTION_TEMPLATES["lieu"],
    **QUESTION_TEMPLATES,
}

DATA_KEYS = {
    "phone": "telephone_assure",
    "vehicle_plate": "plaque",
    "accident_date": "date_accident",
    "accident_time": "heure_accident",
    "location": "lieu",
    "third_party": "tiers_impliques",
    "yes_no": "vehicule_immobilise",
}

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
        "field_records": {},
        "transcript": [f"ASSISTANT: {WELCOME_MESSAGE}"],
        "current_field": "lastname",
        "call_started_at": datetime.now(UTC).isoformat(),
        "pending_confirmation": None,
        "pending_field": None,
        "attempts": {},
        "skipped_fields": [],
        "spelling_mode": False,
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


def _next_field(data: dict, skipped_fields: list[str] | None = None) -> str | None:
    skipped = set(skipped_fields or [])
    return next(
        (
            field
            for field in FLOW
            if field not in skipped and data.get(DATA_KEYS.get(field, field)) is None
        ),
        None,
    )


def progress(data: dict) -> int:
    return round(
        100 * sum(data.get(DATA_KEYS.get(field, field)) is not None for field in FLOW) / len(FLOW)
    )


def _confirmation_prompt(result: dict) -> str:
    value = result.get("normalized")
    if result["slot"] == "location" and result.get("verification_status") == "ambiguous":
        return (
            "Je trouve plusieurs lieux correspondants. Pouvez-vous préciser la commune "
            "ou un repère proche ?"
        )
    if result["slot"] in {"accident_date", "accident_time", "accident_datetime"}:
        return f"J’ai noté {value}. Est-ce correct ?"
    return f"J’ai compris « {value} ». Est-ce correct ?"


def _store_result(state: dict, result: dict) -> None:
    slot = result["slot"]
    state["field_records"][slot] = result
    state["data"][DATA_KEYS.get(slot, slot)] = result["normalized"]
    if state["data"].get("lastname") and state["data"].get("firstname"):
        state["data"]["nom_assure"] = f"{state['data']['firstname']} {state['data']['lastname']}"


def _skip_unusable_field(state: dict, field: str, result: dict, reason: str) -> None:
    """Conserve un échec explicite et permet au parcours d'avancer après deux essais."""
    record = {
        **result,
        "normalized": None,
        "confirmed": False,
        "confidence": 0.0,
        "metadata": {
            **result.get("metadata", {}),
            "collection_status": "missing_after_two_attempts",
            "failure_reason": reason,
            "attempt_count": state["attempts"].get(field, 0),
        },
    }
    state["field_records"][record["slot"]] = record
    state["data"][DATA_KEYS.get(field, field)] = None
    state["skipped_fields"] = [*dict.fromkeys([*state.get("skipped_fields", []), field])]
    state["spelling_mode"] = False


def respond(
    message: str,
    state: dict | None,
    *,
    asr_confidence: float = 0.75,
    location_resolver: LocationResolver | None = None,
    audio_reference: str | None = None,
) -> tuple[str, dict]:
    state = state or new_conversation()
    state = {
        **state,
        "data": dict(state.get("data", {})),
        "field_records": dict(state.get("field_records", {})),
        "attempts": dict(state.get("attempts", {})),
        "skipped_fields": list(state.get("skipped_fields", [])),
    }
    data = state["data"]
    transcript = list(state.get("transcript", []))
    transcript.append(f"CLIENT: {message.strip()}")
    field = state.get("current_field") or _next_field(data, state["skipped_fields"])
    pending = state.get("pending_confirmation")
    if field == "confirmation" and pending:
        answer = parse_yes_no(message)
        if answer is True:
            pending = {**pending, "confirmed": True}
            pending["confidence_components"] = {
                **pending.get("confidence_components", {}),
                "confirmation": 1.0,
            }
            pending["confidence"] = max(float(pending.get("confidence", 0)), 0.95)
            _store_result(state, pending)
            state["pending_confirmation"] = None
            state["pending_field"] = None
            state["spelling_mode"] = False
            field = _next_field(data, state["skipped_fields"])
            reply = (
                f"Merci. {SLOT_QUESTIONS[field]}"
                if field
                else (
                    "Vos informations ont bien été notées. Merci."
                )
            )
        elif answer is False:
            original_slot = state.get("pending_field") or pending["slot"]
            state["pending_confirmation"] = None
            state["pending_field"] = None
            state["attempts"][original_slot] = state["attempts"].get(original_slot, 0) + 1
            if state["attempts"][original_slot] >= 2:
                _skip_unusable_field(
                    state, original_slot, pending, "user_rejected_two_transcriptions"
                )
                field = _next_field(data, state["skipped_fields"])
                reply = (
                    "Je laisse cette information vide et je continue.\n\n"
                    f"{SLOT_QUESTIONS[field]}"
                    if field
                    else (
                        "Vos informations ont bien été notées. Merci."
                    )
                )
            else:
                state["spelling_mode"] = original_slot in {"firstname", "lastname"}
                field = original_slot
                reply = (
                    "Pouvez-vous l’épeler lettre par lettre ?"
                    if state["spelling_mode"]
                    else f"D’accord. {SLOT_QUESTIONS[field]}"
                )
        else:
            original_slot = pending["slot"]
            attempt_key = f"confirmation:{original_slot}"
            state["attempts"][attempt_key] = state["attempts"].get(attempt_key, 0) + 1
            if state["attempts"][attempt_key] >= 2:
                expected_field = state.get("pending_field") or original_slot
                state["attempts"][expected_field] = max(
                    2, state["attempts"].get(expected_field, 0)
                )
                _skip_unusable_field(
                    state, expected_field, pending, "confirmation_not_understood"
                )
                state["pending_confirmation"] = None
                state["pending_field"] = None
                field = _next_field(data, state["skipped_fields"])
                reply = (
                    f"Je n’ai pas pu confirmer cette information ; je la laisse vide. "
                    f"{SLOT_QUESTIONS[field]}"
                    if field
                    else "Je laisse cette information vide. Le recueil est terminé."
                )
            else:
                reply = "Répondez simplement par oui ou non : est-ce correct ?"
        state["current_field"] = field
        transcript.append(f"ASSISTANT: {reply}")
        state["transcript"] = transcript
        return reply, state
    if faq := _faq_answer(message):
        reply = f"{faq}\n\nReprenons la pré-déclaration : {SLOT_QUESTIONS[field]}" if field else faq
    elif not field:
        reply = "La pré-déclaration est complète. Vérifiez le récapitulatif puis créez le dossier."
    else:
        context = {
            "call_started_at": state.get("call_started_at"),
            "spelling_mode": state.get("spelling_mode", False),
            "location_resolver": location_resolver,
            "gps": state.get("gps"),
            "audio_reference": audio_reference,
        }
        result = parse_expected_field(field, message, context, asr_confidence=asr_confidence)
        if result.get("normalized") is None:
            state["attempts"][field] = state["attempts"].get(field, 0) + 1
            if state["attempts"][field] >= 2:
                _skip_unusable_field(state, field, result, "transcription_or_parser_failed")
                field = _next_field(data, state["skipped_fields"])
                reply = (
                    "Je n’ai toujours pas pu comprendre cette information ; je la laisse "
                    f"vide et je continue.\n\n{SLOT_QUESTIONS[field]}"
                    if field
                    else (
                        "Je n’ai toujours pas pu comprendre cette information ; je la laisse "
                        "vide. Vos autres informations ont bien été notées. Merci."
                    )
                )
            elif field in {"firstname", "lastname"}:
                state["spelling_mode"] = True
                reply = "Je n’ai pas bien compris. Pouvez-vous le répéter ou l’épeler ?"
            elif field == "location":
                reply = "Pouvez-vous préciser la commune, le quartier ou un repère proche ?"
            else:
                reply = f"Je n’ai pas pu confirmer cette information. {SLOT_QUESTIONS[field]}"
        elif needs_confirmation(result):
            state["pending_confirmation"] = result
            state["pending_field"] = field
            field = "confirmation"
            reply = _confirmation_prompt(result)
        else:
            _store_result(state, result)
            field = _next_field(data, state["skipped_fields"])
            if field:
                reply = f"Merci, c’est noté.\n\n{SLOT_QUESTIONS[field]}"
            else:
                reply = (
                    "Vos informations ont bien été notées. Merci."
                )
    transcript.append(f"ASSISTANT: {reply}")
    return reply, {
        **state,
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
    data = dict(state.get("data", {}))
    if data.get("firstname") and data.get("lastname"):
        data["nom_assure"] = f"{data['firstname']} {data['lastname']}"
    return ClaimData.model_validate(data)
