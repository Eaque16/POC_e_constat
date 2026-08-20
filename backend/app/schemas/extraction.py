"""Contracts for extracting a structured claim from text."""

from pydantic import BaseModel, Field

from backend.app.schemas.claim import EConstat


class ClaimExtractionRequest(BaseModel):
    transcription: str = Field(min_length=1, max_length=20_000)
    use_llm: bool = False


class CorrectionSuggestion(BaseModel):
    field: str
    heard: str
    suggested: str
    confidence: float = Field(ge=0, le=1)
    confirmation_question: str


class ClaimExtractionResponse(BaseModel):
    claim: EConstat
    extraction_method: str
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    correction_suggestions: list[CorrectionSuggestion] = Field(default_factory=list)
    processing_time_ms: float = Field(ge=0)
