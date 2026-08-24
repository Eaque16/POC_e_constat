from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from econstat.models import (
    ACTIVE_JOB_STATUSES,
    Call,
    Claim,
    ClaimStatus,
    ProcessingJob,
    ProcessingJobStatus,
)
from econstat.schemas.dashboard import DashboardResponse


def _elapsed_seconds(started_at: datetime | None, completed_at: datetime | None) -> float | None:
    if started_at is None or completed_at is None:
        return None
    elapsed = (completed_at - started_at).total_seconds()
    return elapsed if elapsed >= 0 else None


def build_dashboard(db: Session) -> DashboardResponse:
    calls = db.scalars(select(Call)).all()
    claims = db.scalars(select(Claim)).all()
    jobs = db.scalars(select(ProcessingJob)).all()

    active_statuses = set(ACTIVE_JOB_STATUSES) | {ProcessingJobStatus.queued}
    in_progress = sum(job.status in active_statuses for job in jobs)
    failures = [job for job in jobs if job.status == ProcessingJobStatus.failed]
    durations = [
        duration
        for job in jobs
        if job.status == ProcessingJobStatus.ready_for_review
        if (duration := _elapsed_seconds(job.started_at, job.completed_at)) is not None
    ]
    corrected = sum(claim.human_corrections > 0 for claim in claims)
    claim_count = len(claims)

    accident_types: dict[str, int] = {}
    for claim in claims:
        accident_type = str((claim.data_json or {}).get("type_accident") or "non renseigné")
        accident_types[accident_type] = accident_types.get(accident_type, 0) + 1

    error_types: dict[str, int] = {}
    for job in failures:
        error_code = job.error_code or "non_renseignée"
        error_types[error_code] = error_types.get(error_code, 0) + 1

    pending = sum(claim.status == ClaimStatus.pending_validation for claim in claims)
    alerts = []
    if in_progress:
        alerts.append(f"{in_progress} traitement(s) en cours")
    if pending:
        alerts.append(f"{pending} dossier(s) à valider")
    if failures:
        alerts.append(f"{len(failures)} erreur(s) de traitement")

    return DashboardResponse(
        appels=len(calls),
        dossiers=claim_count,
        dossiers_en_cours=in_progress,
        dossiers_a_valider=pending,
        dossiers_valides=sum(claim.status == ClaimStatus.validated for claim in claims),
        dossiers_envoyes=sum(claim.status == ClaimStatus.sent for claim in claims),
        erreurs_traitement=len(failures),
        temps_moyen_traitement_secondes=(
            round(sum(durations) / len(durations), 2) if durations else None
        ),
        taux_dossiers_corriges_pct=(round(corrected / claim_count * 100, 2) if claim_count else 0),
        taux_dossiers_sans_correction_pct=(
            round((claim_count - corrected) / claim_count * 100, 2) if claim_count else 0
        ),
        distribution_types_accident=accident_types,
        distribution_erreurs=error_types,
        alertes=alerts,
    )
