import asyncio
import json

from econstat.config import Settings
from econstat.services.extraction import HybridExtractor, deterministic_extract
from econstat.services.extraction_llm import (
    LLMExtractionOutcome,
    LLMFieldProposal,
    OllamaExtractor,
    literal_evidence_exists,
)


def test_deterministic_nominal_with_literal_evidence(tmp_path):
    transcript = (
        "Je suis Awa Kouamé. Mon numéro est 07 12 34 56 78. Assurée chez NSIA. "
        "Le 24/08/2026 à 14h30 à Cocody, deux véhicules sont impliqués. "
        "Ma plaque est AB 1234 CI. J'ai été percuté à l'arrière du véhicule. "
        "Le pare-chocs est cassé, le véhicule ne roule plus, assistance svp. "
        "Il y a un tiers et aucun blessé."
    )
    settings = Settings(disable_auth=True, enable_llm=False)
    result = asyncio.run(HybridExtractor(settings).extract(transcript, whisper_confidence=0.8))

    assert result.data.nombre_vehicules == 2
    assert result.data.plaque.replace(" ", "") == "AB1234CI"
    assert result.data.vehicule_immobilise is True
    assert result.data.assureur == "NSIA"
    assert result.data.lieu == "Cocody"
    assert result.data.date_accident.isoformat() == "2026-08-24"
    assert result.data.heure_accident.isoformat() == "14:30:00"
    assert result.data.blesses is False
    assert result.trace["llm_status"] == "disabled"
    assert result.evidence["plaque"] in transcript
    assert result.evidence["lieu"] in transcript
    assert all(evidence in transcript for evidence in result.evidence.values())


def test_legacy_deterministic_contract_remains_available():
    data, confidence = deterministic_extract(
        "Deux véhicules sont impliqués. Ma plaque est AB 1234 CI. "
        "Il est immobilisé, assistance svp."
    )
    assert data["nombre_vehicules"] == 2
    assert confidence["plaque"] == 0.94


def test_missing_fields_and_offline_fallback():
    settings = Settings(
        disable_auth=True,
        ollama_base_url="http://127.0.0.1:1",
        llm_timeout_seconds=0.1,
    )
    result = asyncio.run(HybridExtractor(settings).extract("Un véhicule peut rouler."))

    assert result.data.nombre_vehicules == 1
    assert "lieu" in result.missing_fields
    assert result.suggested_questions
    assert result.trace["llm_status"] == "unavailable"


def test_hesitations_do_not_invent():
    data, _ = deterministic_extract("Euh... je crois... enfin je ne sais pas où c'était.")
    assert "lieu" not in data


def test_literal_evidence_guard_is_strict():
    transcript = "L'accident a eu lieu à Cocody."
    assert literal_evidence_exists(transcript, "à Cocody") is True
    assert literal_evidence_exists(transcript, "à Marcory") is False
    assert literal_evidence_exists(transcript, "") is False


def test_ollama_response_rejects_non_literal_and_unknown_fields(monkeypatch):
    response_payload = {
        "fields": {
            "assureur": {"value": "SUNU", "confidence": 0.8, "evidence": "assuré chez SUNU"},
            "lieu": {"value": "Marcory", "confidence": 0.9, "evidence": "à Marcory"},
            "champ_invente": {"value": "x", "confidence": 0.9, "evidence": "SUNU"},
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": json.dumps(response_payload)}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def post(self, _url, json):
            assert json["format"] == "json"
            assert json["options"]["temperature"] == 0
            return FakeResponse()

    monkeypatch.setattr(
        "econstat.services.extraction_llm.httpx.AsyncClient", lambda **_kwargs: FakeClient()
    )
    settings = Settings(disable_auth=True, ollama_enabled=True, enable_llm=True)
    outcome = asyncio.run(OllamaExtractor(settings).extract("Je suis assuré chez SUNU."))

    assert set(outcome.fields) == {"assureur"}
    assert outcome.rejected == {
        "lieu": "evidence_not_literal",
        "champ_invente": "unknown_field",
    }


def test_malformed_ollama_json_is_a_non_blocking_fallback(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "pas du json"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "econstat.services.extraction_llm.httpx.AsyncClient", lambda **_kwargs: FakeClient()
    )
    outcome = asyncio.run(
        OllamaExtractor(Settings(disable_auth=True)).extract("Un accident à Cocody")
    )

    assert outcome.status == "unavailable"
    assert outcome.fields == {}


def test_llm_only_completes_missing_fields_and_schema_is_validated(monkeypatch):
    settings = Settings(disable_auth=True, enable_llm=False)
    extractor = HybridExtractor(settings)

    async def fake_llm(_transcript):
        return LLMExtractionOutcome(
            status="completed",
            fields={
                "plaque": LLMFieldProposal(
                    value="FAUSSE 999", confidence=0.99, evidence="plaque AB 1234 CI"
                ),
                "assureur": LLMFieldProposal(
                    value="SUNU", confidence=0.8, evidence="assuré chez SUNU"
                ),
                "nombre_vehicules": LLMFieldProposal(
                    value=999, confidence=0.8, evidence="999 véhicules"
                ),
            },
            trace={"model": "fake"},
        )

    monkeypatch.setattr(extractor.llm, "extract", fake_llm)
    transcript = "Ma plaque AB 1234 CI, assuré chez SUNU, 999 véhicules."
    result = asyncio.run(extractor.extract(transcript))

    assert result.data.plaque.replace(" ", "") == "AB1234CI"
    assert result.data.assureur == "SUNU"
    assert result.data.nombre_vehicules is None
    assert result.trace["rejected"]["plaque"] == "deterministic_value_kept"
    assert result.trace["rejected"]["nombre_vehicules"] == "schema_validation_failed"
