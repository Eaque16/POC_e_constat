from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from econstat.config import Settings
from econstat.models import (
    AuditLog,
    Claim,
    ClaimStatus,
    ProcessingJob,
    ProcessingJobStatus,
)
from econstat.schemas.claim import ClaimExtraction, TranscriptSegment
from econstat.services.audio_validation import validate_stored_audio
from econstat.services.diarization import Diarizer
from econstat.services.extraction import HybridExtractor
from econstat.services.jobs import advance_job, fail_job
from econstat.services.role_assignment import assign_roles
from econstat.services.transcription import Transcriber, normalise_logprob


async def process_audio(
    audio: Path, settings: Settings
) -> tuple[ClaimExtraction, list[TranscriptSegment]]:
    segments = Transcriber(settings).transcribe(audio)
    diarization = Diarizer(settings).run(audio)
    labelled = assign_roles(segments, diarization.turns).segments
    transcript = "\n".join(f"{segment.speaker}: {segment.text}" for segment in labelled)
    whisper_confidence = (
        sum(normalise_logprob(s.avg_logprob) for s in segments) / len(segments) if segments else 0.0
    )
    extraction = await HybridExtractor(settings).extract(transcript, whisper_confidence)
    return extraction, labelled


def _audit(job: ProcessingJob, action: str, details: dict | None = None) -> AuditLog:
    return AuditLog(
        user_id=None,
        action=action,
        entity_type="processing_job",
        entity_id=job.id,
        details_json=details or {},
    )


async def process_processing_job(db: Session, job: ProcessingJob, settings: Settings) -> None:
    """Exécute un job par checkpoints ; chaque transition valide le résultat précédent."""
    call = job.call
    try:
        if job.status == ProcessingJobStatus.validating_audio:
            probe = validate_stored_audio(Path(call.audio_path), call.audio_sha256 or "", settings)
            db.add(_audit(job, "audio_validated", {"duration_seconds": probe.duration_seconds}))
            advance_job(db, job, ProcessingJobStatus.transcribing)

        if job.status == ProcessingJobStatus.transcribing:
            transcriber = Transcriber(settings, profile=job.profile.value)
            segments = transcriber.transcribe(Path(call.audio_path))
            call.transcript_text = "\n".join(segment.text for segment in segments)
            call.segments_json = [segment.model_dump(mode="json") for segment in segments]
            trace = getattr(transcriber, "last_trace", None)
            trace_details = trace.as_dict() if trace is not None else {}
            db.add(
                _audit(
                    job,
                    "transcription_completed",
                    {"segments": len(segments), **trace_details},
                )
            )
            advance_job(db, job, ProcessingJobStatus.diarizing)

        if job.status == ProcessingJobStatus.diarizing:
            raw_segments = [TranscriptSegment.model_validate(item) for item in call.segments_json]
            diarization = Diarizer(settings).run(Path(call.audio_path))
            assignment = assign_roles(raw_segments, diarization.turns)
            labelled = assignment.segments
            call.segments_json = [segment.model_dump(mode="json") for segment in labelled]
            call.transcript_text = "\n".join(
                f"{segment.speaker}: {segment.text}" for segment in labelled
            )
            db.add(
                _audit(
                    job,
                    "diarization_completed",
                    {
                        **diarization.trace(),
                        **assignment.trace(),
                        "fallback_unknown": not diarization.available,
                        "segments": len(labelled),
                    },
                )
            )
            advance_job(db, job, ProcessingJobStatus.extracting)

        if job.status == ProcessingJobStatus.extracting:
            segment_confidences = [
                float(item.get("confidence", 0)) for item in call.segments_json
            ]
            asr_confidence = (
                sum(segment_confidences) / len(segment_confidences)
                if segment_confidences
                else 0.0
            )
            extraction = await HybridExtractor(settings).extract(
                call.transcript_text or "", asr_confidence
            )
            claim = call.claim or Claim(call_id=call.id)
            claim.data_json = extraction.data.model_dump(mode="json")
            claim.confidence_json = extraction.field_confidences
            claim.evidence_json = extraction.evidence
            claim.missing_fields_json = extraction.missing_fields
            claim.questions_json = extraction.suggested_questions
            claim.global_confidence = extraction.overall_confidence
            claim.model_trace_json = extraction.trace
            claim.status = ClaimStatus.pending_validation
            call.completed_at = datetime.now(UTC)
            db.add(claim)
            db.add(_audit(job, "extraction_completed", {"missing": len(extraction.missing_fields)}))
            advance_job(db, job, ProcessingJobStatus.ready_for_review)
    except Exception as exc:
        db.rollback()
        current = db.get(ProcessingJob, job.id)
        if current is not None:
            error_code = getattr(exc, "code", type(exc).__name__.lower())
            fail_job(db, current, error_code, str(exc) or type(exc).__name__)
        raise
