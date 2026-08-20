from unittest import TestCase
from unittest.mock import patch

from backend.app.api.claims import extract_claim_from_text
from backend.app.schemas.extraction import ClaimExtractionRequest
from backend.app.services.ollama_client import OllamaExtractionError


class ClaimsApiTests(TestCase):
    def test_uses_fast_extraction_by_default(self) -> None:
        request = ClaimExtractionRequest(transcription="Accident à Cocodi")

        with patch("backend.app.api.claims.extract_claim_with_ollama") as ollama:
            response = extract_claim_from_text(request)

        ollama.assert_not_called()
        self.assertEqual(response.extraction_method, "deterministic-fast")
        self.assertIn("assure.nom", response.missing_fields)
        self.assertEqual(response.claim.informations_manquantes, response.missing_fields)
        self.assertEqual(response.correction_suggestions[0].suggested, "Cocody")
        self.assertGreaterEqual(response.processing_time_ms, 0)

    def test_falls_back_when_ollama_is_unavailable(self) -> None:
        request = ClaimExtractionRequest(transcription="Accident à Cocody", use_llm=True)

        with patch(
            "backend.app.api.claims.extract_claim_with_ollama",
            side_effect=OllamaExtractionError("indisponible"),
        ):
            response = extract_claim_from_text(request)

        self.assertEqual(response.extraction_method, "deterministic-fallback")
        self.assertEqual(response.claim.sinistre.lieu, "Cocody")
