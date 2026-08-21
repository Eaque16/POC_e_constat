import re
from pathlib import Path

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment

WELCOME = re.compile(r"bonjour|bienvenue|service sinistre|que puis-je|je vous écoute", re.I)


class Diarizer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline = None

    def _load(self):
        if not self.settings.hf_token:
            raise RuntimeError("HF_TOKEN requis après acceptation des conditions pyannote")
        if self._pipeline is None:
            from pyannote.audio import Pipeline

            local_config = Path("models/pyannote/config.yaml")
            source = str(local_config) if local_config.exists() else self.settings.diarization_model
            self._pipeline = Pipeline.from_pretrained(source, token=self.settings.hf_token)
        return self._pipeline

    def diarize(self, audio: Path) -> list[tuple[float, float, str]]:
        output = self._load()(str(audio), num_speakers=2)
        output = getattr(output, "speaker_diarization", output)
        return [
            (turn.start, turn.end, speaker)
            for turn, _, speaker in output.itertracks(yield_label=True)
        ]


def align_and_label(
    transcript: list[TranscriptSegment],
    turns: list[tuple[float, float, str]],
) -> list[TranscriptSegment]:
    if not turns:
        return [s.model_copy(update={"speaker": "INCONNU"}) for s in transcript]
    raw = []
    for segment in transcript:
        overlaps = [
            (max(0, min(segment.end, end) - max(segment.start, start)), speaker)
            for start, end, speaker in turns
        ]
        raw.append(max(overlaps, default=(0, "INCONNU"))[1])
    agent_raw = next(
        (
            speaker
            for segment, speaker in zip(transcript, raw, strict=True)
            if WELCOME.search(segment.text)
        ),
        raw[0],
    )
    return [
        segment.model_copy(update={"speaker": "AGENT" if speaker == agent_raw else "ASSURE"})
        for segment, speaker in zip(transcript, raw, strict=True)
    ]
