"""Deterministic completeness rules and short follow-up questions."""

from backend.app.schemas.claim import EConstat

CRITICAL_QUESTIONS = (
    ("assure.prenom", "Quel est votre prénom ?"),
    ("assure.nom", "Quel est votre nom de famille ? Pouvez-vous l'épeler ?"),
    ("assure.numero_contrat", "Quel est votre numéro de contrat ou de police ?"),
    ("vehicule.immatriculation", "Quelle est l'immatriculation du véhicule assuré ?"),
    ("sinistre.date_sinistre", "À quelle date l'accident a-t-il eu lieu ?"),
    ("sinistre.lieu", "Où exactement l'accident a-t-il eu lieu ?"),
    ("sinistre.type_sinistre", "Que s'est-il passé : collision, vol ou incendie ?"),
)


def missing_fields_and_questions(claim: EConstat) -> tuple[list[str], list[str]]:
    """Return missing critical paths and questions in conversation order."""

    missing: list[str] = []
    questions: list[str] = []
    for path, question in CRITICAL_QUESTIONS:
        section, field = path.split(".")
        if getattr(getattr(claim, section), field) in (None, ""):
            missing.append(path)
            questions.append(question)
    return missing, questions
