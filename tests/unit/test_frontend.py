import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import httpx

from frontend.app import demo, extract_from_frontend, transcribe_from_frontend


class FrontendTranscriptionTests(TestCase):
    def test_requires_an_audio(self) -> None:
        self.assertEqual(
            transcribe_from_frontend(None),
            ("", {}, "Enregistrez ou importez d'abord un audio."),
        )

    def test_displays_backend_result(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "text": "Accident a Cocody.",
                "language": "fr",
                "language_probability": 0.97,
                "duration": 4.5,
            }

            with patch("frontend.app.httpx.post", return_value=response) as post:
                transcription, metadata, status = transcribe_from_frontend(audio.name)

        self.assertEqual(transcription, "Accident a Cocody.")
        self.assertEqual(metadata["language"], "fr")
        self.assertEqual(metadata["duration_seconds"], 4.5)
        self.assertEqual(status, "Transcription terminee.")
        self.assertEqual(post.call_args.kwargs["timeout"], 600.0)

    def test_reports_backend_unavailability(self) -> None:
        request = httpx.Request("POST", "http://127.0.0.1:8000/audio/transcribe")
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch(
                "frontend.app.httpx.post",
                side_effect=httpx.ConnectError("indisponible", request=request),
            ):
                transcription, metadata, status = transcribe_from_frontend(audio.name)

        self.assertEqual(transcription, "")
        self.assertEqual(metadata, {})
        self.assertIn("Backend indisponible", status)

    def test_builds_gradio_interface(self) -> None:
        configuration = demo.get_config_file()

        component_types = {item["type"] for item in configuration["components"]}
        self.assertIn("audio", component_types)
        self.assertIn("button", component_types)


class FrontendExtractionTests(TestCase):
    def test_requires_a_transcription(self) -> None:
        summary, claim, questions, suggestions, status = extract_from_frontend("")

        self.assertEqual(summary, "")
        self.assertEqual(claim, {})
        self.assertEqual(questions, "")
        self.assertEqual(suggestions, [])
        self.assertIn("Aucune transcription", status)

    def test_displays_important_fields(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "extraction_method": "deterministic-v1",
            "processing_time_ms": 2.4,
            "questions": ["Quel est votre numéro de contrat ?"],
            "correction_suggestions": [],
            "claim": {
                "assure": {
                    "nom": "Kouassi",
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
                    "date_sinistre": "2026-08-19",
                    "heure_sinistre": "08:00:00",
                    "lieu": "Cocody",
                    "description": "Accident à Cocody",
                    "degats": ["phare"],
                },
                "transcription": "Accident à Cocody",
                "informations_manquantes": [],
                "confidence": None,
            },
        }

        with patch("frontend.app.httpx.post", return_value=response):
            summary, claim, questions, suggestions, status = extract_from_frontend("Accident à Cocody")

        self.assertIn("Jean Kouassi", summary)
        self.assertIn("Cocody", summary)
        self.assertEqual(claim["sinistre"]["type_sinistre"], "collision")
        self.assertIn("numéro de contrat", questions)
        self.assertEqual(suggestions, [])
        self.assertIn("deterministic-v1", status)
