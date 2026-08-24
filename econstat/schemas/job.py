from datetime import datetime

from pydantic import BaseModel, ConfigDict

from econstat.models import ProcessingJobStatus, ProcessingProfile


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    call_id: str
    profile: ProcessingProfile
    status: ProcessingJobStatus
    progress_pct: int
    current_step: str
    retry_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    updated_at: datetime
    completed_at: datetime | None


class JobRetryResponse(BaseModel):
    id: str
    status: ProcessingJobStatus
    retry_count: int
