"""Initialisation et migration du mode local Windows sans droits administrateur."""

from pathlib import Path

from sqlalchemy import inspect

from alembic import command
from alembic.config import Config
from econstat.config import get_settings
from econstat.database import SessionLocal, engine
from econstat.seed import seed_demo_users

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_COLUMNS = {
    "users": {"id", "username", "password_hash", "role", "created_at"},
    "calls": {
        "id",
        "agent_id",
        "audio_reference",
        "transcript",
        "segments",
        "duration_seconds",
        "created_at",
        "completed_at",
    },
    "claims": {
        "id",
        "call_id",
        "data",
        "field_confidences",
        "missing_fields",
        "suggested_questions",
        "status",
        "confidence_score",
        "human_edits",
        "model_trace",
        "external_id",
        "validated_by",
        "validated_at",
        "created_at",
        "updated_at",
    },
    "audit_log": {
        "id",
        "user_id",
        "action",
        "entity_type",
        "entity_id",
        "details",
        "created_at",
    },
}


def alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def is_known_unversioned_legacy_schema() -> bool:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables or not tables:
        return False
    if not set(LEGACY_COLUMNS).issubset(tables):
        return False
    return all(
        LEGACY_COLUMNS[table].issubset(
            {column["name"] for column in inspector.get_columns(table)}
        )
        for table in LEGACY_COLUMNS
    )


def migrate_database() -> None:
    config = alembic_config()
    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        if not is_known_unversioned_legacy_schema():
            raise RuntimeError(
                "Base locale non versionnée avec un schéma inconnu. "
                "Aucune migration automatique n'a été tentée."
            )
        command.stamp(config, "0001")
    command.upgrade(config, "head")


def main() -> None:
    migrate_database()
    with SessionLocal() as db:
        created = seed_demo_users(db)
    print(f"Base SQLite migrée et comptes de démonstration prêts (créés : {created}).")


if __name__ == "__main__":
    main()
