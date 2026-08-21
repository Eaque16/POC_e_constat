import math
from pathlib import Path

import torch

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment


def normalise_logprob(avg_logprob: float) -> float:
    return max(0.0, min(1.0, math.exp(avg_logprob)))


class Transcriber:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            self._model = WhisperModel(
                "models/whisper-ct2",
                device=device,
                compute_type=compute_type,
                download_root="models/whisper",
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
