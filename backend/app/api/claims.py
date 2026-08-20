"""Claim extraction HTTP endpoints."""

import logging
import os
from time import perf_counter

from fastapi import APIRouter

from backend.app.schemas.extraction import (
    ClaimExtractionRequest,
    ClaimExtractionResponse,
)
from backend.app.services.extraction import extract_claim
from backend.app.services.claim_questions import missing_fields_and_questions
from backend.app.services.domain_lexicon import find_correction_suggestions
from backend.app.services.ollama_client import (
    OllamaExtractionError,
    extract_claim_with_ollama,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/extract", response_model=ClaimExtractionResponse)
def extract_claim_from_text(request: ClaimExtractionRequest) -> ClaimExtractionResponse:
    """Transform a French accident narrative into the central claim schema."""

    started_at = perf_counter()
    extraction_mode = os.getenv("EXTRACTION_MODE", "deterministic").lower()
    use_llm = request.use_llm or extraction_mode == "ollama"
    if use_llm:
        try:
            claim = extract_claim_with_ollama(request.transcription)
            method = "ollama-hybrid"
        except OllamaExtractionError:
            logger.warning("Ollama indisponible; repli sur l'extraction deterministe")
            method = "deterministic-fallback"
            claim = extract_claim(request.transcription)
    else:
        method = "deterministic-fast"
        claim = extract_claim(request.transcription)

    missing_fields, questions = missing_fields_and_questions(claim)
    claim = claim.model_copy(update={"informations_manquantes": missing_fields})
    return ClaimExtractionResponse(
        claim=claim,
        extraction_method=method,
        missing_fields=missing_fields,
        questions=questions,
        correction_suggestions=find_correction_suggestions(claim),
        processing_time_ms=round((perf_counter() - started_at) * 1000, 2),
    )
