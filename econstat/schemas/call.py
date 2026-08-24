from pydantic import BaseModel


class CallUploadResponse(BaseModel):
    id: str
    status: str
    duration_seconds: float
    sha256: str
