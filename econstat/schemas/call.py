from pydantic import BaseModel


class CallUploadResponse(BaseModel):
    id: str
    status: str
    job_id: str
    job_status: str
    duration_seconds: float
    sha256: str
