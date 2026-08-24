from typing import Literal

from pydantic import BaseModel, Field

from econstat.schemas.claim import TranscriptSegment


class CallUploadResponse(BaseModel):
    id: str
    status: str
    job_id: str
    job_status: str
    duration_seconds: float
    sha256: str


class SpeakerCorrection(BaseModel):
    segment_index: int = Field(ge=0)
    speaker: Literal["AGENT", "ASSURE", "INCONNU"]


class SpeakerCorrectionsRequest(BaseModel):
    corrections: list[SpeakerCorrection] = Field(min_length=1)


class SpeakerCorrectionsResponse(BaseModel):
    call_id: str
    corrected_segments: int
    segments: list[TranscriptSegment]
