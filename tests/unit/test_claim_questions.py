from backend.app.schemas.claim import Assure, EConstat, Sinistre, Vehicule
from backend.app.services.claim_questions import missing_fields_and_questions
from backend.app.services.domain_lexicon import find_correction_suggestions


def test_prioritizes_missing_critical_information() -> None:
    claim = EConstat(
        assure=Assure(prenom="Jean", nom="Kouassi"),
        vehicule=Vehicule(),
        sinistre=Sinistre(lieu="Cocody", type_sinistre="collision"),
    )

    missing, questions = missing_fields_and_questions(claim)

    assert missing == [
        "assure.numero_contrat",
        "vehicule.immatriculation",
        "sinistre.date_sinistre",
    ]
    assert len(questions) == 3


def test_suggests_but_does_not_replace_ivoirian_entities() -> None:
    claim = EConstat(
        assure=Assure(prenom="Jean", nom="Kouasi"),
        vehicule=Vehicule(),
        sinistre=Sinistre(lieu="Cocodi"),
    )

    suggestions = find_correction_suggestions(claim)

    assert claim.assure.nom == "Kouasi"
    assert claim.sinistre.lieu == "Cocodi"
    assert {(item.field, item.suggested) for item in suggestions} == {
        ("assure.nom", "Kouassi"),
        ("sinistre.lieu", "Cocody"),
    }
