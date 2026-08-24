"""Align the domain schema and add persistent processing jobs."""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def create_index_if_missing(name: str, table: str, columns: list[str], unique: bool = False):
    existing = {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=unique)


def drop_index_if_present(name: str, table: str):
    existing = {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}
    if name in existing:
        op.drop_index(name, table_name=table)


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", new_column_name="hashed_password")

    with op.batch_alter_table("calls") as batch:
        batch.alter_column("agent_id", new_column_name="owner_id")
        batch.alter_column("audio_reference", new_column_name="audio_path")
        batch.alter_column("transcript", new_column_name="transcript_text")
        batch.alter_column("segments", new_column_name="segments_json")
        batch.add_column(sa.Column("audio_sha256", sa.String(64), nullable=True))
    create_index_if_missing("ix_calls_owner_id", "calls", ["owner_id"])
    create_index_if_missing("ix_calls_audio_sha256", "calls", ["audio_sha256"])

    with op.batch_alter_table("claims") as batch:
        batch.alter_column("data", new_column_name="data_json")
        batch.alter_column("field_confidences", new_column_name="confidence_json")
        batch.alter_column("missing_fields", new_column_name="missing_fields_json")
        batch.alter_column("suggested_questions", new_column_name="questions_json")
        batch.alter_column("confidence_score", new_column_name="global_confidence")
        batch.alter_column("human_edits", new_column_name="human_corrections")
        batch.alter_column("model_trace", new_column_name="model_trace_json")
        batch.add_column(
            sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch.create_unique_constraint("uq_claims_external_id", ["external_id"])
    create_index_if_missing("ix_claims_call_id", "claims", ["call_id"], unique=True)
    create_index_if_missing("ix_claims_validated_by", "claims", ["validated_by"])

    with op.batch_alter_table("audit_log") as batch:
        batch.alter_column("details", new_column_name="details_json")
    create_index_if_missing("ix_audit_log_user_id", "audit_log", ["user_id"])
    create_index_if_missing("ix_audit_log_action", "audit_log", ["action"])
    create_index_if_missing("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("call_id", sa.String(36), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column(
            "profile",
            sa.Enum("fast", "quality", name="processingprofile"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "validating_audio",
                "transcribing",
                "diarizing",
                "extracting",
                "ready_for_review",
                "failed",
                "cancelled",
                name="processingjobstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(100), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100", name="ck_job_progress_pct"
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_job_retry_count"),
    )
    op.create_index("ix_processing_jobs_call_id", "processing_jobs", ["call_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index(
        "ix_processing_jobs_claimable", "processing_jobs", ["status", "updated_at"]
    )


def downgrade():
    op.drop_index("ix_processing_jobs_claimable", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_call_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")

    drop_index_if_present("ix_audit_log_entity_id", "audit_log")
    drop_index_if_present("ix_audit_log_action", "audit_log")
    drop_index_if_present("ix_audit_log_user_id", "audit_log")
    with op.batch_alter_table("audit_log") as batch:
        batch.alter_column("details_json", new_column_name="details")

    drop_index_if_present("ix_claims_validated_by", "claims")
    drop_index_if_present("ix_claims_call_id", "claims")
    with op.batch_alter_table("claims") as batch:
        batch.drop_constraint("uq_claims_external_id", type_="unique")
        batch.drop_column("evidence_json")
        batch.alter_column("model_trace_json", new_column_name="model_trace")
        batch.alter_column("human_corrections", new_column_name="human_edits")
        batch.alter_column("global_confidence", new_column_name="confidence_score")
        batch.alter_column("questions_json", new_column_name="suggested_questions")
        batch.alter_column("missing_fields_json", new_column_name="missing_fields")
        batch.alter_column("confidence_json", new_column_name="field_confidences")
        batch.alter_column("data_json", new_column_name="data")

    drop_index_if_present("ix_calls_audio_sha256", "calls")
    drop_index_if_present("ix_calls_owner_id", "calls")
    with op.batch_alter_table("calls") as batch:
        batch.drop_column("audio_sha256")
        batch.alter_column("segments_json", new_column_name="segments")
        batch.alter_column("transcript_text", new_column_name="transcript")
        batch.alter_column("audio_path", new_column_name="audio_reference")
        batch.alter_column("owner_id", new_column_name="agent_id")

    with op.batch_alter_table("users") as batch:
        batch.alter_column("hashed_password", new_column_name="password_hash")
