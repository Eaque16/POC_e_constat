from econstat.config import Settings
from econstat.services.extraction import HybridExtractor, deterministic_extract


def test_deterministic_nominal():
    data, confidence = deterministic_extract(
        "Deux véhicules sont impliqués. Ma plaque est AB 1234 CI. "
        "Il est immobilisé, assistance svp."
    )
    assert data["nombre_vehicules"] == 2
    assert data["plaque"].replace(" ", "") == "AB1234CI"
    assert data["vehicule_immobilise"] is True
    assert confidence["plaque"] == 0.9


def test_missing_fields_and_offline_fallback():
    settings = Settings(ollama_base_url="http://127.0.0.1:1")
    import asyncio

    result = asyncio.run(HybridExtractor(settings).extract("Un véhicule peut rouler."))
    assert result.data.nombre_vehicules == 1
    assert "lieu" in result.missing_fields
    assert result.suggested_questions


def test_hesitations_do_not_invent():
    data, _ = deterministic_extract("Euh... je crois... enfin je ne sais pas où c'était.")
    assert "lieu" not in data
