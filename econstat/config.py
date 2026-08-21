from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite:///./econstat.db"
    jwt_secret: str = "dev-only-secret-change-me-32-characters"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    hf_token: str | None = None
    whisper_model: str = "bofenghuang/whisper-large-v3-french"
    whisper_revision: str = "e0e885752469ae13df3c68b2bc35b3fbe6293ae6"
    whisper_distil_model: str = "bofenghuang/whisper-large-v3-french-distil-dec16"
    whisper_distil_revision: str = "16bd02185bdaa6b00fb4b0deb46e47ac1b754b8e"
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    diarization_revision: str = "main"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_cpu: str = "qwen3:4b"
    ollama_model_8gb: str = "qwen3:8b"
    ollama_model_16gb: str = "qwen3:14b"
    ollama_model_20gb: str = "qwen3.6:27b"
    vram_threshold_8b_gb: float = 8
    vram_threshold_14b_gb: float = 16
    vram_threshold_27b_gb: float = 20
    llm_temperature: float = 0.0
    enable_llm: bool = True
    disable_auth: bool = False
    random_seed: int = 42
    econsta_base_url: str = "http://localhost:8001"
    econsta_api_key: str = "demo-local-key"
    upload_dir: Path = Field(default=Path("data/uploads"))
    pdf_dir: Path = Field(default=Path("generated"))
    lexicon_path: Path = Field(default=Path("data/lexique_ci.json"))
    allow_model_downloads: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
