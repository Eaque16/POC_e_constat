from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TranscriptSegment(BaseModel):
    start: float
    end: float
    speaker: Literal["AGENT", "ASSURE", "INCONNU"] = "INCONNU"
    text: str
    avg_logprob: float = -1.0


class ThirdParty(BaseModel):
    nom: str | None = None
    telephone: str | None = None
    plaque: str | None = None
    assureur: str | None = None


class ClaimData(BaseModel):
    nom_assure: str | None = None
    telephone_assure: str | None = None
    lieu: str | None = None
    date_accident: date | None = None
    heure_accident: time | None = None
    type_accident: str | None = None
    nombre_vehicules: int | None = Field(default=None, ge=1, le=20)
    dommages: str | None = None
    zone_endommagee: str | None = None
    vehicule_immobilise: bool | None = None
    plaque: str | None = None
    besoin_assistance: bool | None = None
    tiers: list[ThirdParty] = Field(default_factory=list)
    circonstances: str | None = None

    @field_validator("plaque")
    @classmethod
    def normalise_plaque(cls, value: str | None) -> str | None:
        return " ".join(value.upper().split()) if value else value


class ExtractedValue(BaseModel):
    value: object | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: str | None = None


class ClaimExtraction(BaseModel):
    data: ClaimData
    field_confidences: dict[str, float] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0, le=1)
    trace: dict = Field(default_factory=dict)


REQUIRED_FIELDS = (
    "nom_assure",
    "lieu",
    "date_accident",
    "heure_accident",
    "type_accident",
    "nombre_vehicules",
    "dommages",
    "zone_endommagee",
    "vehicule_immobilise",
    "plaque",
    "besoin_assistance",
    "circonstances",
)

QUESTION_TEMPLATES = {
    "nom_assure": "Pouvez-vous confirmer votre nom complet ?",
    "lieu": "Où l'accident s'est-il produit précisément ?",
    "date_accident": "À quelle date l'accident a-t-il eu lieu ?",
    "heure_accident": "À quelle heure environ l'accident a-t-il eu lieu ?",
    "type_accident": "Quel type de collision s'est produit ?",
    "nombre_vehicules": "Combien de véhicules sont impliqués ?",
    "dommages": "Quels dommages constatez-vous ?",
    "zone_endommagee": "Quelle partie du véhicule est endommagée ?",
    "vehicule_immobilise": "Le véhicule peut-il encore rouler ?",
    "plaque": "Quelle est l'immatriculation de votre véhicule ?",
    "besoin_assistance": "Avez-vous besoin d'une assistance ou d'un remorquage ?",
    "circonstances": "Pouvez-vous décrire les circonstances de l'accident ?",
}
