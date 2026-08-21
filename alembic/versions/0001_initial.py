"""Initial schema."""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    role = sa.Enum("agent", "responsable", name="role")
    status = sa.Enum("draft", "pending_validation", "validated", "sent", name="claimstatus")
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", role),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("audio_reference", sa.String(500)),
        sa.Column("transcript", sa.Text),
        sa.Column("segments", sa.JSON),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("call_id", sa.String(36), sa.ForeignKey("calls.id"), unique=True),
        sa.Column("data", sa.JSON),
        sa.Column("field_confidences", sa.JSON),
        sa.Column("missing_fields", sa.JSON),
        sa.Column("suggested_questions", sa.JSON),
        sa.Column("status", status),
        sa.Column("confidence_score", sa.Float),
        sa.Column("human_edits", sa.Integer),
        sa.Column("model_trace", sa.JSON),
        sa.Column("external_id", sa.String(100)),
        sa.Column("validated_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100)),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.String(36)),
        sa.Column("details", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("audit_log")
    op.drop_table("claims")
    op.drop_table("calls")
    op.drop_table("users")
    sa.Enum(name="claimstatus").drop(op.get_bind())
    sa.Enum(name="role").drop(op.get_bind())
