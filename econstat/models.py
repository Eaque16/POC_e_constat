import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from econstat.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(str, enum.Enum):
    agent = "agent"
    responsable = "responsable"


class ClaimStatus(str, enum.Enum):
    draft = "draft"
    pending_validation = "pending_validation"
    validated = "validated"
    sent = "sent"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.agent)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Call(Base):
    __tablename__ = "calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    audio_reference: Mapped[str | None] = mapped_column(String(500))
    transcript: Mapped[str | None] = mapped_column(Text)
    segments: Mapped[list] = mapped_column(JSON, default=list)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim: Mapped["Claim | None"] = relationship(back_populates="call", uselist=False)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    field_confidences: Mapped[dict] = mapped_column(JSON, default=dict)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    suggested_questions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus), default=ClaimStatus.draft)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    human_edits: Mapped[int] = mapped_column(Integer, default=0)
    model_trace: Mapped[dict] = mapped_column(JSON, default=dict)
    external_id: Mapped[str | None] = mapped_column(String(100))
    validated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    call: Mapped[Call] = relationship(back_populates="claim")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
