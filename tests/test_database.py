import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from econstat.database import Base
from econstat.models import (
    AuditLog,
    Call,
    Claim,
    ClaimStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingProfile,
    Role,
    User,
)


def test_crud_for_domain_entities(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crud.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(username="agent.test", hashed_password="not-a-real-hash", role=Role.agent)
        call = Call(
            owner=user,
            audio_path="data/uploads/test.wav",
            audio_sha256="a" * 64,
            segments_json=[],
        )
        job = ProcessingJob(
            call=call,
            profile=ProcessingProfile.fast,
            status=ProcessingJobStatus.queued,
            progress_pct=0,
            current_step="queued",
        )
        claim = Claim(
            call=call,
            data_json={"plaque": "AB 1234 CI"},
            confidence_json={"plaque": 0.9},
            evidence_json={"plaque": "ma plaque est AB 1234 CI"},
            missing_fields_json=["lieu"],
            questions_json=["Où l'accident s'est-il produit ?"],
            status=ClaimStatus.pending_validation,
        )
        db.add_all([user, call, job, claim])
        db.flush()
        audit = AuditLog(
            user_id=None,
            action="call_created",
            entity_type="call",
            entity_id=call.id,
            details_json={"source": "test"},
        )
        db.add(audit)
        db.commit()

        saved = db.scalar(select(Call).where(Call.id == call.id))
        assert saved is not None
        assert saved.owner_id == user.id
        assert saved.agent_id == user.id
        assert saved.audio_reference == saved.audio_path
        assert saved.claim is not None
        assert saved.claim.data == saved.claim.data_json
        assert saved.jobs[0].status == ProcessingJobStatus.queued
        assert saved.jobs[0].retry_count == 0


def test_processing_job_rejects_invalid_progress(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'constraint.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(username="constraint.test", hashed_password="test", role=Role.agent)
        call = Call(owner=user, audio_path="test.wav", segments_json=[])
        job = ProcessingJob(call=call, progress_pct=101, current_step="invalid")
        db.add(job)
        with pytest.raises(IntegrityError):
            db.commit()


def run_alembic(project_root, database_url: str, *arguments: str) -> None:
    environment = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_migration_upgrade_downgrade_round_trip(tmp_path):
    project_root = os.path.dirname(os.path.dirname(__file__))
    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"

    run_alembic(project_root, database_url, "upgrade", "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "processing_jobs" in inspector.get_table_names()
    assert "owner_id" in {column["name"] for column in inspector.get_columns("calls")}
    assert "evidence_json" in {column["name"] for column in inspector.get_columns("claims")}

    run_alembic(project_root, database_url, "downgrade", "0001")
    inspector = inspect(create_engine(database_url))
    assert "processing_jobs" not in inspector.get_table_names()
    assert "agent_id" in {column["name"] for column in inspector.get_columns("calls")}

    run_alembic(project_root, database_url, "upgrade", "head")
    assert "processing_jobs" in inspect(create_engine(database_url)).get_table_names()


def test_bootstrap_adopts_known_unversioned_legacy_database(tmp_path):
    project_root = os.path.dirname(os.path.dirname(__file__))
    database_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    environment = {**os.environ, "DATABASE_URL": database_url}

    run_alembic(project_root, database_url, "upgrade", "0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE INDEX ix_audit_log_action ON audit_log (action)")
        connection.exec_driver_sql("DROP TABLE alembic_version")

    for _ in range(2):
        subprocess.run(
            [sys.executable, "-m", "econstat.local_bootstrap"],
            cwd=project_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    inspector = inspect(engine)
    assert "processing_jobs" in inspector.get_table_names()
    with engine.connect() as connection:
        count = connection.exec_driver_sql("SELECT COUNT(*) FROM users").scalar_one()
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    assert count == 2
    assert revision == "0002"
