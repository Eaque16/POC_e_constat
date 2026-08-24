import math
from pathlib import Path

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment


def normalise_logprob(avg_logprob: float) -> float:
    return max(0.0, min(1.0, math.exp(avg_logprob)))


class Transcriber:
    def __init__(self, settings: Settings, profile: str | None = None):
        self.settings = settings
        selected_profile = profile or settings.processing_profile
        self.model_source = Path(
            settings.whisper_quality_model
            if selected_profile == "quality"
            else settings.whisper_fast_model
        )
        self._model = None

    def _load(self):
        if self._model is None:
            if not self.model_source.exists() and not self.settings.allow_model_downloads:
                raise RuntimeError(
                    f"Modèle Whisper local absent : {self.model_source}. "
                    "Utilisez scripts/download_models.py explicitement."
                )
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                str(self.model_source),
                device=self.settings.whisper_device,
                compute_type=self.settings.whisper_compute_type,
                download_root=str(self.settings.model_dir / "whisper"),
            )
        return self._model

    def transcribe(self, audio: Path) -> list[TranscriptSegment]:
        segments, _ = self._load().transcribe(
            str(audio),
            language="fr",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=True,
        )
        return [
            TranscriptSegment(
                start=s.start,
                end=s.end,
                text=s.text.strip(),
                avg_logprob=s.avg_logprob,
            )
            for s in segments
        ]
