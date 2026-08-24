from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from econstat.database import Base
from econstat.models import (
    Call,
    Claim,
    ClaimStatus,
    ProcessingJob,
    ProcessingJobStatus,
    Role,
    User,
)
from econstat.services.dashboard import build_dashboard


def test_dashboard_computes_all_manager_metrics(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as db:
        owner = User(username="dashboard.agent", hashed_password="hash", role=Role.agent)
        calls = [Call(owner=owner, audio_path=f"demo://{index}") for index in range(4)]
        db.add_all(
            [
                Claim(
                    call=calls[0],
                    status=ClaimStatus.pending_validation,
                    human_corrections=1,
                    data_json={"type_accident": "collision arrière"},
                ),
                Claim(
                    call=calls[1],
                    status=ClaimStatus.validated,
                    human_corrections=0,
                    data_json={"type_accident": "collision arrière"},
                ),
                Claim(
                    call=calls[2],
                    status=ClaimStatus.sent,
                    human_corrections=2,
                    data_json={},
                ),
                ProcessingJob(
                    call=calls[0], status=ProcessingJobStatus.queued
                ),
                ProcessingJob(
                    call=calls[1], status=ProcessingJobStatus.extracting
                ),
                ProcessingJob(
                    call=calls[2],
                    status=ProcessingJobStatus.ready_for_review,
                    started_at=now - timedelta(seconds=30),
                    completed_at=now,
                ),
                ProcessingJob(
                    call=calls[3],
                    status=ProcessingJobStatus.failed,
                    error_code="model_missing",
                    started_at=now - timedelta(seconds=90),
                    completed_at=now,
                ),
            ]
        )
        db.commit()

        result = build_dashboard(db)

    assert result.appels == 4
    assert result.dossiers == 3
    assert result.dossiers_en_cours == 2
    assert result.dossiers_a_valider == 1
    assert result.dossiers_valides == 1
    assert result.dossiers_envoyes == 1
    assert result.erreurs_traitement == 1
    assert result.temps_moyen_traitement_secondes == 30
    assert result.taux_dossiers_corriges_pct == 66.67
    assert result.taux_dossiers_sans_correction_pct == 33.33
    assert result.distribution_types_accident == {
        "collision arrière": 2,
        "non renseigné": 1,
    }
    assert result.distribution_erreurs == {"model_missing": 1}
    assert len(result.alertes) == 3


def test_empty_dashboard_has_no_fake_average_or_alert(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty-dashboard.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = build_dashboard(db)

    assert result.appels == 0
    assert result.dossiers == 0
    assert result.temps_moyen_traitement_secondes is None
    assert result.taux_dossiers_corriges_pct == 0
    assert result.taux_dossiers_sans_correction_pct == 0
    assert result.alertes == []
