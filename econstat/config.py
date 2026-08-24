from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=("settings_",)
    )

    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite:///./econstat-local.db"
    jwt_secret: str = "dev-only-secret-change-me-32-characters"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 480
    hf_token: str | None = None
    upload_dir: Path = Field(default=Path("data/uploads"))
    recordings_dir: Path = Field(default=Path("data/recordings"))
    generated_dir: Path = Field(default=Path("generated"))
    model_dir: Path = Field(default=Path("models"))
    lexicon_path: Path = Field(default=Path("data/lexique_ci.json"))
    max_audio_mb: int = 100
    max_audio_duration_seconds: int = 7200
    allowed_audio_extensions: str = ".wav,.mp3,.m4a,.ogg,.flac"
    allow_model_downloads: bool = False
    processing_profile: str = "fast"
    job_stale_minutes: int = 30
    job_poll_seconds: float = 2.0
    job_max_retries: int = 3
    whisper_fast_model: str = "models/whisper-tiny"
    whisper_quality_model: str = "models/whisper-ct2"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = "fr"
    whisper_fast_beam_size: int = 1
    whisper_quality_beam_size: int = 5
    whisper_model: str = "bofenghuang/whisper-large-v3-french"
    whisper_revision: str = "e0e885752469ae13df3c68b2bc35b3fbe6293ae6"
    whisper_distil_model: str = "bofenghuang/whisper-large-v3-french-distil-dec16"
    whisper_distil_revision: str = "16bd02185bdaa6b00fb4b0deb46e47ac1b754b8e"
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    diarization_revision: str = "main"
    diarization_num_speakers: int = 2
    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
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
    llm_seed: int = 42
    econsta_base_url: str = "http://127.0.0.1:8001"
    econsta_api_key: str = "demo-local-key"

    @property
    def access_token_minutes(self) -> int:
        """Compatibilité avec le service d'authentification historique."""
        return self.jwt_expiration_minutes

    @property
    def pdf_dir(self) -> Path:
        """Compatibilité avec le générateur PDF historique."""
        return self.generated_dir

    @property
    def random_seed(self) -> int:
        """Compatibilité avec l'extracteur historique."""
        return self.llm_seed

    @property
    def allowed_audio_suffixes(self) -> frozenset[str]:
        return frozenset(
            suffix.strip().lower()
            for suffix in self.allowed_audio_extensions.split(",")
            if suffix.strip()
        )

    @model_validator(mode="after")
    def validate_required_secrets(self) -> "Settings":
        if not self.disable_auth and not self.jwt_secret.strip():
            raise ValueError(
                "JWT_SECRET est obligatoire lorsque DISABLE_AUTH=false. "
                "Renseignez-le dans le fichier .env local."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
