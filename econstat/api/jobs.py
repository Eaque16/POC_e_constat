from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from econstat.api.deps import current_user, get_owned_job_or_404
from econstat.config import get_settings
from econstat.database import get_db
from econstat.models import Call, ProcessingJob, Role, User
from econstat.schemas.job import JobResponse, JobRetryResponse
from econstat.services.jobs import JobTransitionError, retry_failed_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    statement = select(ProcessingJob).join(Call).order_by(ProcessingJob.updated_at.desc())
    if user.role == Role.agent:
        statement = statement.where(Call.owner_id == user.id)
    return db.scalars(statement).all()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return get_owned_job_or_404(job_id, user, db)


@router.post("/{job_id}/retry", response_model=JobRetryResponse)
def retry_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    job = get_owned_job_or_404(job_id, user, db)
    try:
        retry_failed_job(db, job, get_settings().job_max_retries)
    except JobTransitionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return JobRetryResponse(id=job.id, status=job.status, retry_count=job.retry_count)
