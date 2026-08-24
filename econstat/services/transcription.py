"""Transcription Faster-Whisper locale, CPU-first et traçable."""

from __future__ import annotations

import math
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment
from econstat.services.lexicon import LocalLexicon

REQUIRED_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json")
CONFIDENCE_METHOD = "exp(avg_logprob), borné entre 0 et 1; indicateur ASR non calibré métier"
_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()


class TranscriptionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TranscriptionTrace:
    profile: str
    model_path: str
    device: str
    compute_type: str
    language: str
    beam_size: int
    vad_filter: bool
    elapsed_seconds: float
    audio_duration_seconds: float | None
    realtime_factor: float | None
    average_segment_confidence: float
    confidence_method: str = CONFIDENCE_METHOD

    def as_dict(self) -> dict:
        return asdict(self)


def normalise_logprob(avg_logprob: float) -> float:
    """Transforme un log-score moyen en indicateur borné, sans calibration métier."""
    if not math.isfinite(avg_logprob):
        return 0.0
    return round(max(0.0, min(1.0, math.exp(avg_logprob))), 4)


def local_model_missing_files(path: Path) -> tuple[str, ...]:
    return tuple(filename for filename in REQUIRED_MODEL_FILES if not (path / filename).is_file())


def clear_model_cache() -> None:
    """Réservé aux tests et diagnostics contrôlés."""
    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE.clear()


class Transcriber:
    def __init__(self, settings: Settings, profile: str | None = None):
        self.settings = settings
        self.profile = profile or settings.processing_profile
        if self.profile not in {"fast", "quality"}:
            raise TranscriptionError(
                "whisper_profile_invalid", f"Profil Whisper inconnu : {self.profile}"
            )
        self.model_source = Path(
            settings.whisper_quality_model
            if self.profile == "quality"
            else settings.whisper_fast_model
        )
        self.beam_size = (
            settings.whisper_quality_beam_size
            if self.profile == "quality"
            else settings.whisper_fast_beam_size
        )
        self.last_trace: TranscriptionTrace | None = None

    def _load(self):
        missing = local_model_missing_files(self.model_source)
        if missing:
            raise TranscriptionError(
                "whisper_model_incomplete",
                f"Modèle Whisper local incomplet ({self.model_source}) : {', '.join(missing)}. "
                "Utilisez scripts/download_models.py explicitement.",
            )
        key = (
            str(self.model_source.resolve()),
            self.settings.whisper_device,
            self.settings.whisper_compute_type,
        )
        with _MODEL_CACHE_LOCK:
            model = _MODEL_CACHE.get(key)
            if model is None:
                from faster_whisper import WhisperModel

                try:
                    model = WhisperModel(
                        str(self.model_source),
                        device=self.settings.whisper_device,
                        compute_type=self.settings.whisper_compute_type,
                        local_files_only=not self.settings.allow_model_downloads,
                    )
                except Exception as exc:
                    raise TranscriptionError(
                        "whisper_model_load_failed",
                        f"Chargement du modèle Whisper impossible : {type(exc).__name__}",
                    ) from exc
                _MODEL_CACHE[key] = model
        return model

    def transcribe(self, audio: Path) -> list[TranscriptSegment]:
        if not audio.is_file():
            raise TranscriptionError("audio_file_missing", "Fichier audio introuvable.")
        started = perf_counter()
        try:
            vocabulary = LocalLexicon(self.settings.lexicon_path).speech_vocabulary()
            # Le modèle tiny ne dispose que de 448 positions. Un prompt trop long fait
            # échouer la génération avant même la première transcription.
            hotwords = ", ".join(vocabulary)[:500]
            raw_segments, info = self._load().transcribe(
                str(audio),
                language=self.settings.whisper_language,
                beam_size=self.beam_size,
                vad_filter=True,
                condition_on_previous_text=True,
                initial_prompt="Déclaration automobile en Côte d’Ivoire.",
                hotwords=hotwords,
            )
            segments = [
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text.strip(),
                    avg_logprob=float(segment.avg_logprob),
                    confidence=normalise_logprob(float(segment.avg_logprob)),
                )
                for segment in raw_segments
                if segment.text.strip()
            ]
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                "whisper_transcription_failed",
                f"Transcription Whisper impossible : {type(exc).__name__}",
            ) from exc
        elapsed = perf_counter() - started
        duration_value = getattr(info, "duration", None)
        audio_duration = float(duration_value) if duration_value is not None else None
        average = sum(segment.confidence for segment in segments) / len(segments) if segments else 0
        self.last_trace = TranscriptionTrace(
            profile=self.profile,
            model_path=str(self.model_source),
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
            language=self.settings.whisper_language,
            beam_size=self.beam_size,
            vad_filter=True,
            elapsed_seconds=round(elapsed, 3),
            audio_duration_seconds=round(audio_duration, 3) if audio_duration else None,
            realtime_factor=(round(elapsed / audio_duration, 3) if audio_duration else None),
            average_segment_confidence=round(average, 4),
        )
        return segments
