from pydantic import BaseModel, Field


class DashboardResponse(BaseModel):
    appels: int = Field(ge=0)
    dossiers: int = Field(ge=0)
    dossiers_en_cours: int = Field(ge=0)
    dossiers_a_valider: int = Field(ge=0)
    dossiers_valides: int = Field(ge=0)
    dossiers_envoyes: int = Field(ge=0)
    erreurs_traitement: int = Field(ge=0)
    temps_moyen_traitement_secondes: float | None = Field(default=None, ge=0)
    taux_dossiers_corriges_pct: float = Field(ge=0, le=100)
    taux_dossiers_sans_correction_pct: float = Field(ge=0, le=100)
    distribution_types_accident: dict[str, int]
    distribution_erreurs: dict[str, int]
    alertes: list[str]
