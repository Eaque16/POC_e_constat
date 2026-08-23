import pytest
from pydantic import ValidationError

from econstat.config import Settings


def test_cpu_first_defaults():
    settings = Settings(_env_file=None)

    assert settings.whisper_device == "cpu"
    assert settings.whisper_compute_type == "int8"
    assert settings.processing_profile == "fast"
    assert settings.allow_model_downloads is False


def test_jwt_secret_is_required_when_authentication_is_enabled():
    with pytest.raises(ValidationError, match="JWT_SECRET est obligatoire"):
        Settings(_env_file=None, jwt_secret="", disable_auth=False)
