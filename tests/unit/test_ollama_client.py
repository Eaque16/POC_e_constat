import json
from unittest import TestCase
from unittest.mock import Mock, patch

import httpx

from backend.app.services.ollama_client import (
    OllamaExtractionError,
    build_extraction_prompt,
    extract_claim_with_ollama,
)


class OllamaClientTests(TestCase):
    def test_prompt_forbids_invention(self) -> None:
        prompt = build_extraction_prompt("Accident à Cocody")

        self.assertIn("N'invente jamais", prompt)
        self.assertIn("Accident à Cocody", prompt)

    def test_validates_structured_response_and_preserves_source(self) -> None:
        model_claim = {
            "assure": {
                "nom": None,
                "prenom": "Jean",
                "telephone": None,
                "numero_contrat": None,
            },
            "vehicule": {
                "immatriculation": None,
                "marque": None,
                "modele": None,
            },
            "sinistre": {
                "type_sinistre": "collision",
                "date_sinistre": "2023-04-05",
                "heure_sinistre": None,
                "lieu": "Cocody",
                "degats": [],
            },
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {"content": json.dumps(model_claim)}
        }

        with patch("backend.app.services.ollama_client.httpx.post", return_value=response):
            claim = extract_claim_with_ollama(
                "Je m'appelle Jean Kouassi, accident à Cocody avec le phare cassé"
            )

        self.assertEqual(claim.assure.prenom, "Jean")
        self.assertEqual(claim.assure.nom, "Kouassi")
        self.assertEqual(claim.sinistre.lieu, "Cocody")
        self.assertIsNone(claim.sinistre.date_sinistre)
        self.assertEqual(claim.sinistre.degats, ["phare"])
        self.assertEqual(
            claim.transcription,
            "Je m'appelle Jean Kouassi, accident à Cocody avec le phare cassé",
        )

    def test_wraps_connection_error(self) -> None:
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
        with patch(
            "backend.app.services.ollama_client.httpx.post",
            side_effect=httpx.ConnectError("absent", request=request),
        ):
            with self.assertRaises(OllamaExtractionError):
                extract_claim_with_ollama("Accident")
