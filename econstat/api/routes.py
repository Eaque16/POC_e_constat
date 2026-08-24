from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from econstat.api.deps import (
    current_user,
    get_owned_call_or_404,
    get_owned_claim_or_404,
    responsable,
)
from econstat.config import get_settings
from econstat.database import get_db
from econstat.models import (
    AuditLog,
    Call,
    Claim,
    ClaimStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingProfile,
    User,
)
from econstat.schemas.call import CallUploadResponse
from econstat.schemas.claim import ClaimData
from econstat.schemas.job import JobResponse
from econstat.services.audio_validation import AudioValidationError, validate_and_store_audio
from econstat.services.econsta import EConstaClient
from econstat.services.extraction import HybridExtractor
from econstat.services.jobs import create_job
from econstat.services.pdf import generate_claim_pdf

router = APIRouter()


class ClaimUpdate(BaseModel):
    data: ClaimData


class TranscriptRequest(BaseModel):
    transcript: str


@router.post("/calls", status_code=201, response_model=CallUploadResponse)
async def create_call(
    audio: UploadFile = File(...),
    profile: ProcessingProfile = Form(ProcessingProfile.fast),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CallUploadResponse:
    settings = get_settings()
    try:
        stored = validate_and_store_audio(audio, settings)
    except AudioValidationError as exc:
        db.add(
            AuditLog(
                user_id=user.id,
                action="audio_upload_rejected",
                entity_type="call",
                entity_id="upload-rejected",
                details_json={"error_code": exc.code},
            )
        )
        db.commit()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.detail},
        ) from exc

    call = Call(
        id=stored.storage_id,
        owner_id=user.id,
        audio_path=str(stored.path),
        audio_sha256=stored.sha256,
        duration_seconds=stored.duration_seconds,
        segments_json=[],
    )
    db.add(call)
    job = create_job(call.id, profile)
    db.add(job)
    db.add(
        AuditLog(
            user_id=user.id,
            action="audio_uploaded",
            entity_type="call",
            entity_id=call.id,
            details_json={
                "size_bytes": stored.size_bytes,
                "duration_seconds": stored.duration_seconds,
                "mime_type": stored.mime_type,
                "format_name": stored.format_name,
                "sha256": stored.sha256,
            },
        )
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="job_queued",
            entity_type="processing_job",
            entity_id=job.id,
            details_json={"call_id": call.id, "profile": profile.value},
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        stored.path.unlink(missing_ok=True)
        raise
    return CallUploadResponse(
        id=call.id,
        status="uploaded",
        job_id=job.id,
        job_status=ProcessingJobStatus.queued.value,
        duration_seconds=stored.duration_seconds,
        sha256=stored.sha256,
    )


@router.post("/calls/{call_id}/extract")
async def extract_call(
    call_id: str, transcript: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_owned_call_or_404(call_id, user, db)
    raise HTTPException(
        409, "Extraction directe désactivée : utilisez le job asynchrone de l’appel."
    )


@router.post("/calls/{call_id}/transcribe")
def transcribe_call(
    call_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_owned_call_or_404(call_id, user, db)
    raise HTTPException(409, "Transcription directe désactivée : utilisez le worker.")


@router.post("/calls/demo", status_code=201)
async def create_demo_call(
    body: TranscriptRequest, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Parcours de secours sans poids STT : transcript fourni et réellement persisté."""
    result = await HybridExtractor(get_settings()).extract(body.transcript)
    call = Call(
        owner_id=user.id,
        audio_path="demo://transcript",
        transcript_text=body.transcript,
        completed_at=datetime.now(UTC),
    )
    db.add(call)
    db.flush()
    claim = Claim(
        call_id=call.id,
        data=result.data.model_dump(mode="json"),
        field_confidences=result.field_confidences,
        missing_fields=result.missing_fields,
        suggested_questions=result.suggested_questions,
        confidence_score=result.overall_confidence,
        model_trace=result.trace,
        status=ClaimStatus.pending_validation,
    )
    db.add(claim)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="demo_extraction",
            entity_type="claim",
            entity_id=claim.id,
            details=result.trace,
        )
    )
    db.commit()
    return {"claim_id": claim.id, "call_id": call.id, "extraction": result}


@router.post("/calls/{call_id}/process", response_model=JobResponse)
def process_call_audio(
    call_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Compatibilité : retourne le job existant sans lancer de calcul dans la requête."""
    call = get_owned_call_or_404(call_id, user, db)
    job = db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.call_id == call.id)
        .order_by(ProcessingJob.updated_at.desc())
    )
    if job is None:
        raise HTTPException(409, "Aucun job associé à cet appel.")
    return job


@router.get("/claims")
def list_claims(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Claim).join(Call).order_by(Claim.created_at.desc())
    if user.role.value == "agent":
        stmt = stmt.where(Call.owner_id == user.id)
    return db.scalars(stmt).all()


@router.put("/claims/{claim_id}")
def update_claim(
    claim_id: str,
    body: ClaimUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    claim = get_owned_claim_or_404(claim_id, user, db)
    claim.data = body.data.model_dump(mode="json")
    claim.human_edits += 1
    db.add(
        AuditLog(
            user_id=user.id,
            action="human_edit",
            entity_type="claim",
            entity_id=claim.id,
            details={},
        )
    )
    db.commit()
    return claim


@router.post("/claims/{claim_id}/validate")
def validate_claim(
    claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    claim = get_owned_claim_or_404(claim_id, user, db)
    claim.status = ClaimStatus.validated
    claim.validated_by = user.id
    claim.validated_at = datetime.now(UTC)
    db.add(
        AuditLog(
            user_id=user.id,
            action="human_validation",
            entity_type="claim",
            entity_id=claim.id,
            details={},
        )
    )
    db.commit()
    return {"status": "validated", "validated_by": user.username}


@router.post("/claims/{claim_id}/send")
async def send_claim(
    claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    claim = get_owned_claim_or_404(claim_id, user, db)
    if claim.status != ClaimStatus.validated or not claim.validated_by:
        raise HTTPException(409, "Une validation humaine explicite est obligatoire")
    result = await EConstaClient(get_settings()).create_claim(claim.id, claim.data, True)
    claim.external_id = result["id"]
    claim.status = ClaimStatus.sent
    db.add(
        AuditLog(
            user_id=user.id,
            action="sent_to_econsta",
            entity_type="claim",
            entity_id=claim.id,
            details={"external_id": claim.external_id},
        )
    )
    db.commit()
    return result


@router.get("/claims/{claim_id}/pdf")
def claim_pdf(claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    claim = get_owned_claim_or_404(claim_id, user, db)
    if claim.status not in {ClaimStatus.validated, ClaimStatus.sent}:
        raise HTTPException(409, "Le PDF exige une validation humaine")
    return {"path": str(generate_claim_pdf(claim.id, claim.data, get_settings().pdf_dir))}


@router.get("/dashboard")
def dashboard(_: User = Depends(responsable), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Call.id))) or 0
    claims = db.scalar(select(func.count(Claim.id))) or 0
    validated = (
        db.scalar(
            select(func.count(Claim.id)).where(
                Claim.status.in_([ClaimStatus.validated, ClaimStatus.sent])
            )
        )
        or 0
    )
    edits = db.scalar(select(func.sum(Claim.human_edits))) or 0
    durations = [v for v in db.scalars(select(Call.duration_seconds)).all() if v is not None]
    all_claims = db.scalars(select(Claim)).all()
    motifs: dict[str, int] = {}
    for claim in all_claims:
        motif = claim.data.get("type_accident") or "non renseigné"
        motifs[motif] = motifs.get(motif, 0) + 1
    pending = claims - validated
    return {
        "appels": total,
        "declarations": claims,
        "validees": validated,
        "en_attente": pending,
        "temps_moyen_secondes": round(sum(durations) / len(durations), 1) if durations else None,
        "part_sans_edition_humaine": round(1 - edits / max(claims, 1), 2),
        "motifs": motifs,
        "alertes": ["Dossiers en attente à traiter"] if pending else [],
    }
