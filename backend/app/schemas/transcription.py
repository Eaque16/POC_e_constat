"""Pydantic contracts for audio transcription endpoints."""

from pydantic import BaseModel, Field


class TranscriptionSegment(BaseModel):
    """Timestamped speech segment without an inferred speaker identity."""

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str


class TranscriptionResponse(BaseModel):
    """Structured metadata returned after a successful transcription."""

    text: str
    language: str
    language_probability: float = Field(ge=0, le=1)
    duration: float = Field(ge=0)
    segments: list[TranscriptionSegment] = Field(default_factory=list)
