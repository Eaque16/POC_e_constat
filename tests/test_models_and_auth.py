from econstat.config import Settings
from econstat.schemas.claim import ClaimData
from econstat.services.auth import create_token, decode_token, hash_password, verify_password
from econstat.services.model_selector import select_qwen_model


def test_vram_model_thresholds():
    settings = Settings()
    assert select_qwen_model(settings, 7).model == settings.ollama_model_cpu
    assert select_qwen_model(settings, 8).model == settings.ollama_model_8gb
    assert select_qwen_model(settings, 16).model == settings.ollama_model_16gb
    assert select_qwen_model(settings, 20).model == settings.ollama_model_20gb


def test_claim_normalizes_plate():
    assert ClaimData(plaque="ab   1234 ci").plaque == "AB 1234 CI"


def test_lightweight_jwt():
    settings = Settings(jwt_secret="test-secret-that-is-long-enough-1234")
    password_hash = hash_password("secret")
    assert verify_password("secret", password_hash)
    token = create_token("u1", "agent", settings)
    assert decode_token(token, settings)["role"] == "agent"
