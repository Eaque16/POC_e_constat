from datetime import date, time
from typing import Optional, List

from pydantic import BaseModel, Field


class Assure(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    telephone: Optional[str] = None
    numero_contrat: Optional[str] = None


class Vehicule(BaseModel):
    immatriculation: Optional[str] = None
    marque: Optional[str] = None
    modele: Optional[str] = None


class Sinistre(BaseModel):
    type_sinistre: Optional[str] = None
    date_sinistre: Optional[date] = None
    heure_sinistre: Optional[time] = None

    lieu: Optional[str] = None
    description: Optional[str] = None

    degats: List[str] = Field(default_factory=list)


class EConstat(BaseModel):
    assure: Assure
    vehicule: Vehicule
    sinistre: Sinistre

    transcription: Optional[str] = None

    informations_manquantes: List[str] = Field(default_factory=list)

    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )
