"""ASR interactif local, partagé et instrumenté par processus UI."""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment
from econstat.services.lexicon import LocalLexicon
from econstat.services.transcription import Transcriber, TranscriptionError, normalise_logprob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RealtimeMetrics:
    cold_start_ms: float
    model_load_ms: float
    audio_decode_ms: float
    vad_ms: float
    asr_ms: float
    parser_ms: float = 0.0
    geocoder_ms: float = 0.0
    persistence_ms: float = 0.0
    total_turn_ms: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RealtimeTranscript:
    segments: list[TranscriptSegment]
    metrics: RealtimeMetrics

    @property
    def text(self) -> str:
        return " ".join(segment.text for segment in self.segments).strip()

    @property
    def confidence(self) -> float:
        if not self.segments:
            return 0.0
        return round(sum(item.confidence for item in self.segments) / len(self.segments), 4)


class RealtimeTranscriber:
    def __init__(self, settings: Settings, mode: str = "fast"):
        if mode not in {"fast", "precision"}:
            raise ValueError(f"Mode ASR interactif inconnu : {mode}")
        self.mode = mode
        model_path = (
            settings.whisper_small_model if mode == "precision" else settings.whisper_fast_model
        )
        self.settings = settings.model_copy(update={"whisper_fast_model": model_path})
        self._transcriber = Transcriber(self.settings, profile="fast")
        self._ready = False
        self._load_lock = threading.Lock()
        self._model_load_ms = 0.0

    def load(self):
        with self._load_lock:
            if self._ready:
                return self._transcriber._load()
            logger.info("ASR model loading... mode=%s", self.mode)
            started = perf_counter()
            model = self._transcriber._load()
            self._model_load_ms = (perf_counter() - started) * 1000
            self._ready = True
            logger.info("ASR model ready")
            return model

    def warm_up(self) -> None:
        if not self.settings.realtime_asr_warmup:
            return
        try:
            import numpy as np

            model = self.load()
            segments, _ = model.transcribe(
                np.zeros(16000, dtype=np.float32),
                language="fr",
                beam_size=1,
                vad_filter=False,
                without_timestamps=True,
                word_timestamps=False,
            )
            list(segments)
            logger.info("ASR warm-up complete")
        except TranscriptionError:
            logger.warning("ASR warm-up unavailable: local model missing or invalid")
        except Exception as exc:
            logger.warning("ASR warm-up failed: %s", type(exc).__name__)

    def transcribe(
        self, audio_path: Path, *, context: str | None = None
    ) -> RealtimeTranscript:
        if not audio_path.is_file():
            raise TranscriptionError("audio_file_missing", "Fichier audio introuvable.")
        total_started = perf_counter()
        was_ready = self._ready
        model = self.load()
        cold_start_ms = 0.0 if was_ready else self._model_load_ms
        try:
            from faster_whisper.audio import decode_audio
            from faster_whisper.vad import collect_chunks, get_speech_timestamps

            decode_started = perf_counter()
            audio = decode_audio(str(audio_path), sampling_rate=16000)
            decode_ms = (perf_counter() - decode_started) * 1000
            vad_started = perf_counter()
            speech = get_speech_timestamps(audio)
            speech_audio = collect_chunks(audio, speech) if speech else audio
            vad_ms = (perf_counter() - vad_started) * 1000
            vocabulary = LocalLexicon(self.settings.lexicon_path).speech_vocabulary()
            asr_started = perf_counter()
            prompt = "Déclaration automobile en Côte d’Ivoire, en français."
            if context:
                prompt += f" Question posée : {context}"
            raw_segments, _ = model.transcribe(
                speech_audio,
                language="fr",
                beam_size=5 if self.mode == "precision" else 1,
                vad_filter=False,
                condition_on_previous_text=True,
                initial_prompt=prompt,
                hotwords=", ".join(vocabulary)[:500],
                word_timestamps=False,
                temperature=0.0,
            )
            segments = [
                TranscriptSegment(
                    start=float(item.start),
                    end=float(item.end),
                    text=item.text.strip(),
                    avg_logprob=float(item.avg_logprob),
                    confidence=normalise_logprob(float(item.avg_logprob)),
                )
                for item in raw_segments
                if item.text.strip()
            ]
            asr_ms = (perf_counter() - asr_started) * 1000
        except Exception as exc:
            raise TranscriptionError(
                "whisper_transcription_failed",
                f"Transcription Whisper impossible : {type(exc).__name__}",
            ) from exc
        metrics = RealtimeMetrics(
            cold_start_ms=round(cold_start_ms, 1),
            model_load_ms=round(self._model_load_ms, 1),
            audio_decode_ms=round(decode_ms, 1),
            vad_ms=round(vad_ms, 1),
            asr_ms=round(asr_ms, 1),
            total_turn_ms=round((perf_counter() - total_started) * 1000, 1),
        )
        logger.info(
            "ASR turn cold_start_ms=%.1f model_load_ms=%.1f audio_decode_ms=%.1f "
            "vad_ms=%.1f asr_ms=%.1f",
            metrics.cold_start_ms,
            metrics.model_load_ms,
            metrics.audio_decode_ms,
            metrics.vad_ms,
            metrics.asr_ms,
        )
        return RealtimeTranscript(segments, metrics)


_REALTIME: dict[str, RealtimeTranscriber] = {}
_REALTIME_LOCK = threading.Lock()


def get_realtime_transcriber(
    settings: Settings, mode: str | None = None
) -> RealtimeTranscriber:
    selected = mode or settings.realtime_asr_default_mode
    with _REALTIME_LOCK:
        if selected not in _REALTIME:
            _REALTIME[selected] = RealtimeTranscriber(settings, selected)
        return _REALTIME[selected]
