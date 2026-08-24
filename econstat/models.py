import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from econstat.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid4_string() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    agent = "agent"
    responsable = "responsable"


class ClaimStatus(str, enum.Enum):
    draft = "draft"
    pending_validation = "pending_validation"
    validated = "validated"
    sent = "sent"


class ProcessingProfile(str, enum.Enum):
    fast = "fast"
    quality = "quality"


class ProcessingJobStatus(str, enum.Enum):
    queued = "queued"
    validating_audio = "validating_audio"
    transcribing = "transcribing"
    diarizing = "diarizing"
    extracting = "extracting"
    ready_for_review = "ready_for_review"
    failed = "failed"
    cancelled = "cancelled"


ACTIVE_JOB_STATUSES = frozenset(
    {
        ProcessingJobStatus.validating_audio,
        ProcessingJobStatus.transcribing,
        ProcessingJobStatus.diarizing,
        ProcessingJobStatus.extracting,
    }
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_string)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    password_hash = synonym("hashed_password")
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.agent)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    calls: Mapped[list["Call"]] = relationship(back_populates="owner")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    agent_id = synonym("owner_id")
    audio_path: Mapped[str | None] = mapped_column(String(500))
    audio_reference = synonym("audio_path")
    audio_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    transcript = synonym("transcript_text")
    segments_json: Mapped[list] = mapped_column(JSON, default=list)
    segments = synonym("segments_json")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="calls", foreign_keys=[owner_id])
    claim: Mapped["Claim | None"] = relationship(
        back_populates="call", uselist=False, cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_string)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), unique=True, index=True)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    data = synonym("data_json")
    confidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    field_confidences = synonym("confidence_json")
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    missing_fields_json: Mapped[list] = mapped_column(JSON, default=list)
    missing_fields = synonym("missing_fields_json")
    questions_json: Mapped[list] = mapped_column(JSON, default=list)
    suggested_questions = synonym("questions_json")
    status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus), default=ClaimStatus.draft)
    global_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score = synonym("global_confidence")
    human_corrections: Mapped[int] = mapped_column(Integer, default=0)
    human_edits = synonym("human_corrections")
    model_trace_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_trace = synonym("model_trace_json")
    validated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    call: Mapped[Call] = relationship(back_populates="claim")
    validator: Mapped[User | None] = relationship(foreign_keys=[validated_by])


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100", name="ck_job_progress_pct"
        ),
        CheckConstraint("retry_count >= 0", name="ck_job_retry_count"),
        Index("ix_processing_jobs_claimable", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_string)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    profile: Mapped[ProcessingProfile] = mapped_column(
        Enum(ProcessingProfile), default=ProcessingProfile.fast
    )
    status: Mapped[ProcessingJobStatus] = mapped_column(
        Enum(ProcessingJobStatus), default=ProcessingJobStatus.queued, index=True
    )
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str] = mapped_column(String(100), default="queued")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    call: Mapped[Call] = relationship(back_populates="jobs")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    details = synonym("details_json")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
