from datetime import date
from unittest import TestCase
from unittest.mock import patch

from backend.app.services.extraction import extract_claim


class ClaimExtractionTests(TestCase):
    def test_extracts_location_after_relative_date(self) -> None:
        claim = extract_claim("J'ai eu une collision aujourd'hui à Cocodi.")

        self.assertEqual(claim.sinistre.lieu, "Cocodi")

    def test_extracts_explicit_information_from_reference_story(self) -> None:
        transcription = (
            "Bonjour, je m'appelle Jean Kouassi. J'ai eu un accident aujourd'hui "
            "vers 8 heures à Cocody. Une voiture m'a percuté à l'avant et mon phare "
            "droit ainsi que mon pare-chocs sont endommagés."
        )

        with patch("backend.app.services.extraction.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 8, 19)
            claim = extract_claim(transcription)

        self.assertEqual(claim.assure.prenom, "Jean")
        self.assertEqual(claim.assure.nom, "Kouassi")
        self.assertEqual(claim.sinistre.date_sinistre, date(2026, 8, 19))
        self.assertEqual(claim.sinistre.heure_sinistre.hour, 8)
        self.assertEqual(claim.sinistre.lieu, "Cocody")
        self.assertEqual(claim.sinistre.type_sinistre, "collision")
        self.assertEqual(claim.sinistre.degats, ["pare-chocs", "phare"])
        self.assertIsNone(claim.vehicule.immatriculation)
        self.assertIsNone(claim.assure.numero_contrat)

    def test_does_not_invent_absent_information(self) -> None:
        claim = extract_claim("Mon véhicule est endommagé.")

        self.assertIsNone(claim.assure.nom)
        self.assertIsNone(claim.assure.prenom)
        self.assertIsNone(claim.sinistre.lieu)
        self.assertIsNone(claim.sinistre.date_sinistre)
        self.assertIsNone(claim.vehicule.immatriculation)

    def test_ignores_invalid_date(self) -> None:
        claim = extract_claim("L'accident date du 32/13/2026.")

        self.assertIsNone(claim.sinistre.date_sinistre)
