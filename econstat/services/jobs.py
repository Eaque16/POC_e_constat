"""File SQL persistante et transitions contrôlées des traitements."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from econstat.models import (
    ACTIVE_JOB_STATUSES,
    AuditLog,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingProfile,
    uuid4_string,
)

STEP_PROGRESS = {
    ProcessingJobStatus.queued: 0,
    ProcessingJobStatus.validating_audio: 10,
    ProcessingJobStatus.transcribing: 25,
    ProcessingJobStatus.diarizing: 60,
    ProcessingJobStatus.extracting: 80,
    ProcessingJobStatus.ready_for_review: 100,
}
ACTIVE_VALUES = tuple(status.value for status in ACTIVE_JOB_STATUSES)


class JobTransitionError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def create_job(call_id: str, profile: ProcessingProfile) -> ProcessingJob:
    return ProcessingJob(
        id=uuid4_string(),
        call_id=call_id,
        profile=profile,
        status=ProcessingJobStatus.queued,
        progress_pct=0,
        current_step=ProcessingJobStatus.queued.value,
    )


def recover_stale_jobs(db: Session, stale_minutes: int, now: datetime | None = None) -> int:
    current_time = now or utcnow()
    cutoff = current_time - timedelta(minutes=stale_minutes)
    stale_jobs = db.scalars(
        select(ProcessingJob).where(
            ProcessingJob.status.in_(ACTIVE_VALUES),
            ProcessingJob.updated_at < cutoff,
        )
    ).all()
    for job in stale_jobs:
        previous_status = job.status.value
        job.status = ProcessingJobStatus.queued
        job.locked_at = None
        job.retry_count += 1
        job.error_code = "job_stale_recovered"
        job.error_message = "Traitement interrompu remis en file automatiquement."
        job.updated_at = current_time
        db.add(
            AuditLog(
                user_id=None,
                action="job_stale_recovered",
                entity_type="processing_job",
                entity_id=job.id,
                details_json={"resume_step": job.current_step, "previous_status": previous_status},
            )
        )
    if stale_jobs:
        db.commit()
    return len(stale_jobs)


def _queued_jobs_query() -> Select[tuple[ProcessingJob]]:
    return (
        select(ProcessingJob)
        .where(ProcessingJob.status == ProcessingJobStatus.queued)
        .order_by(ProcessingJob.updated_at.asc(), ProcessingJob.id.asc())
    )


def claim_next_job(db: Session, now: datetime | None = None) -> ProcessingJob | None:
    """Réserve un job avec un UPDATE conditionnel, sûr face à deux workers concurrents."""
    current_time = now or utcnow()
    for candidate in db.scalars(_queued_jobs_query()).all():
        resume_status = (
            ProcessingJobStatus(candidate.current_step)
            if candidate.current_step in ACTIVE_VALUES
            else ProcessingJobStatus.validating_audio
        )
        result = db.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.id == candidate.id,
                ProcessingJob.status == ProcessingJobStatus.queued,
            )
            .values(
                status=resume_status,
                current_step=resume_status.value,
                progress_pct=max(candidate.progress_pct, STEP_PROGRESS[resume_status]),
                locked_at=current_time,
                started_at=candidate.started_at or current_time,
                updated_at=current_time,
                error_code=None,
                error_message=None,
            )
        )
        if result.rowcount == 1:
            db.add(
                AuditLog(
                    user_id=None,
                    action="job_started",
                    entity_type="processing_job",
                    entity_id=candidate.id,
                    details_json={"step": resume_status.value},
                )
            )
            db.commit()
            return db.get(ProcessingJob, candidate.id)
        db.rollback()
    return None


def advance_job(
    db: Session,
    job: ProcessingJob,
    status: ProcessingJobStatus,
    progress_pct: int | None = None,
) -> ProcessingJob:
    if status not in ACTIVE_JOB_STATUSES and status != ProcessingJobStatus.ready_for_review:
        raise JobTransitionError(f"Étape de progression invalide : {status.value}")
    progress = STEP_PROGRESS[status] if progress_pct is None else progress_pct
    if progress < job.progress_pct or not 0 <= progress <= 100:
        raise JobTransitionError("La progression doit être croissante et comprise entre 0 et 100.")
    now = utcnow()
    job.status = status
    job.current_step = status.value
    job.progress_pct = progress
    job.updated_at = now
    if status == ProcessingJobStatus.ready_for_review:
        job.completed_at = now
        job.locked_at = None
    db.commit()
    return job


def fail_job(db: Session, job: ProcessingJob, code: str, message: str) -> ProcessingJob:
    job.status = ProcessingJobStatus.failed
    job.error_code = code[:100]
    job.error_message = message[:1000]
    job.locked_at = None
    job.updated_at = utcnow()
    db.add(
        AuditLog(
            user_id=None,
            action="job_failed",
            entity_type="processing_job",
            entity_id=job.id,
            details_json={"error_code": job.error_code, "step": job.current_step},
        )
    )
    db.commit()
    return job


def retry_failed_job(db: Session, job: ProcessingJob, max_retries: int) -> ProcessingJob:
    if job.status != ProcessingJobStatus.failed:
        raise JobTransitionError("Seul un job en échec peut être relancé.")
    if job.retry_count >= max_retries:
        raise JobTransitionError("Nombre maximal de relances atteint.")
    job.retry_count += 1
    job.status = ProcessingJobStatus.queued
    job.locked_at = None
    job.completed_at = None
    job.error_code = None
    job.error_message = None
    job.updated_at = utcnow()
    db.add(
        AuditLog(
            user_id=None,
            action="job_retried",
            entity_type="processing_job",
            entity_id=job.id,
            details_json={"retry_count": job.retry_count, "resume_step": job.current_step},
        )
    )
    db.commit()
    return job
