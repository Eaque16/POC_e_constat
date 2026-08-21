from pathlib import Path

from econstat.config import Settings
from econstat.schemas.claim import ClaimExtraction, TranscriptSegment
from econstat.services.diarization import Diarizer, align_and_label
from econstat.services.extraction import HybridExtractor
from econstat.services.transcription import Transcriber, normalise_logprob


async def process_audio(
    audio: Path, settings: Settings
) -> tuple[ClaimExtraction, list[TranscriptSegment]]:
    segments = Transcriber(settings).transcribe(audio)
    try:
        turns = Diarizer(settings).diarize(audio)
    except RuntimeError:
        turns = []
    labelled = align_and_label(segments, turns)
    transcript = "\n".join(f"{segment.speaker}: {segment.text}" for segment in labelled)
    whisper_confidence = (
        sum(normalise_logprob(s.avg_logprob) for s in segments) / len(segments) if segments else 0.0
    )
    extraction = await HybridExtractor(settings).extract(transcript, whisper_confidence)
    return extraction, labelled
