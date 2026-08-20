"""Local audio transcription with Faster-Whisper."""

import os
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from faster_whisper import WhisperModel

from backend.app.services.domain_lexicon import whisper_domain_prompt

ALLOWED_AUDIO_EXTENSIONS = {".m4a", ".mp3", ".ogg", ".wav", ".webm"}


class TranscriptionSegment(TypedDict):
    """One timestamped speech segment (not yet speaker-labelled)."""

    start: float
    end: float
    text: str


class TranscriptionResult(TypedDict):
    """Stable result returned to API and UI layers."""

    text: str
    language: str
    language_probability: float
    duration: float
    segments: list[TranscriptionSegment]


@lru_cache(maxsize=1)
def get_whisper_model() -> WhisperModel:
    """Load the local model once, when the first transcription is requested."""

    return WhisperModel(
        os.getenv("MODEL_NAME", "small"),
        device=os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
    )


def validate_audio_path(audio_path: str | Path) -> Path:
    """Return a resolved valid audio path or raise an explicit error."""

    path = Path(audio_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Fichier audio introuvable : {path}")
    if path.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        raise ValueError(f"Format audio non pris en charge. Formats autorises : {allowed}")
    return path.resolve()


def transcribe_audio(audio_path: str | Path) -> TranscriptionResult:
    """Transcribe a supported local audio file in French."""

    path = validate_audio_path(audio_path)
    initial_prompt = os.getenv("WHISPER_INITIAL_PROMPT") or None
    # Faster-Whisper reserves up to 223 tokens for each of ``hotwords`` and
    # ``initial_prompt``. Supplying both can create a 450-token decoder prompt,
    # already beyond Whisper's 448-position limit. Prefer an explicitly
    # configured initial prompt; otherwise use the domain lexicon as hotwords.
    hotwords = None if initial_prompt else (
        os.getenv("WHISPER_HOTWORDS") or whisper_domain_prompt()
    )
    segments_iterator, info = get_whisper_model().transcribe(
        str(path),
        language="fr",
        beam_size=int(os.getenv("WHISPER_BEAM_SIZE", "3")),
        # Keep generation below Whisper's 448-position decoder limit. Without
        # this explicit cap, some CTranslate2/model combinations attempt to
        # access position 448 and fail before returning the first segment.
        max_new_tokens=int(os.getenv("WHISPER_MAX_NEW_TOKENS", "128")),
        vad_filter=True,
        condition_on_previous_text=False,
        hotwords=hotwords,
        initial_prompt=initial_prompt,
    )
    segments = [
        {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        }
        for segment in segments_iterator
        if segment.text.strip()
    ]
    transcription = " ".join(segment["text"] for segment in segments)

    return {
        "text": transcription,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": segments,
    }
