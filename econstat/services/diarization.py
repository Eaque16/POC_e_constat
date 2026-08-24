"""Diarisation pyannote facultative avec fallback explicite et traçable."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment
from econstat.services.role_assignment import assign_roles

_PIPELINE_CACHE: dict[str, Any] = {}
_PIPELINE_CACHE_LOCK = threading.Lock()


@dataclass(frozen=True)
class DiarizationOutcome:
    turns: list[tuple[float, float, str]]
    available: bool
    status: str
    reason: str | None
    model_source: str
    elapsed_seconds: float

    def trace(self) -> dict:
        return {**asdict(self), "turns": len(self.turns)}


def clear_diarization_cache() -> None:
    with _PIPELINE_CACHE_LOCK:
        _PIPELINE_CACHE.clear()


class Diarizer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.local_config = settings.model_dir / "pyannote" / "config.yaml"

    def _source(self) -> tuple[str | None, str | None]:
        if self.local_config.is_file():
            return str(self.local_config), None
        if not self.settings.hf_token:
            return None, "hf_token_missing"
        if not self.settings.allow_model_downloads:
            return None, "local_model_missing_downloads_disabled"
        return self.settings.diarization_model, None

    def _load(self, source: str):
        with _PIPELINE_CACHE_LOCK:
            pipeline = _PIPELINE_CACHE.get(source)
            if pipeline is None:
                from pyannote.audio import Pipeline

                pipeline = Pipeline.from_pretrained(
                    source,
                    use_auth_token=self.settings.hf_token,
                    cache_dir=self.settings.model_dir / "pyannote-cache",
                )
                if pipeline is None:
                    raise RuntimeError("Pipeline pyannote non chargé; accès ou licence à vérifier.")
                _PIPELINE_CACHE[source] = pipeline
        return pipeline

    def run(self, audio: Path) -> DiarizationOutcome:
        started = perf_counter()
        source, unavailable_reason = self._source()
        if unavailable_reason:
            return DiarizationOutcome(
                turns=[],
                available=False,
                status="fallback",
                reason=unavailable_reason,
                model_source=self.settings.diarization_model,
                elapsed_seconds=round(perf_counter() - started, 3),
            )
        try:
            output = self._load(source)(
                str(audio), num_speakers=self.settings.diarization_num_speakers
            )
            annotation = getattr(output, "speaker_diarization", output)
            turns = [
                (float(turn.start), float(turn.end), str(speaker))
                for turn, _, speaker in annotation.itertracks(yield_label=True)
            ]
        except Exception as exc:
            return DiarizationOutcome(
                turns=[],
                available=False,
                status="fallback",
                reason=f"pyannote_{type(exc).__name__.lower()}",
                model_source=source,
                elapsed_seconds=round(perf_counter() - started, 3),
            )
        return DiarizationOutcome(
            turns=turns,
            available=True,
            status="completed",
            reason=None,
            model_source=source,
            elapsed_seconds=round(perf_counter() - started, 3),
        )

    def diarize(self, audio: Path) -> list[tuple[float, float, str]]:
        """Compatibilité : retourne les tours, éventuellement vides en fallback."""
        return self.run(audio).turns


def align_and_label(
    transcript: list[TranscriptSegment], turns: list[tuple[float, float, str]]
) -> list[TranscriptSegment]:
    """Compatibilité avec l’ancien contrat, déléguée au service d’attribution."""
    return assign_roles(transcript, turns).segments
