import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from econstat.api.deps import current_user, responsable
from econstat.config import get_settings
from econstat.database import get_db
from econstat.models import AuditLog, Call, Claim, ClaimStatus, User
from econstat.schemas.claim import ClaimData
from econstat.services.auth import create_token, verify_password
from econstat.services.diarization import Diarizer, align_and_label
from econstat.services.econsta import EConstaClient
from econstat.services.extraction import HybridExtractor
from econstat.services.pdf import generate_claim_pdf
from econstat.services.pipeline import process_audio
from econstat.services.transcription import Transcriber

router = APIRouter()


class ClaimUpdate(BaseModel):
    data: ClaimData


class TranscriptRequest(BaseModel):
    transcript: str


@router.post("/auth/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Identifiants invalides")
    return {
        "access_token": create_token(user.id, user.role.value, get_settings()),
        "token_type": "bearer",
    }


@router.post("/calls", status_code=201)
async def create_call(
    audio: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)
):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    call = Call(agent_id=user.id, audio_reference="pending")
    db.add(call)
    db.flush()
    suffix = Path(audio.filename or "audio.wav").suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
        raise HTTPException(415, "Format audio non pris en charge")
    target = settings.upload_dir / f"{call.id}{suffix}"
    with target.open("wb") as stream:
        shutil.copyfileobj(audio.file, stream)
    call.audio_reference = str(target)
    db.commit()
    return {"id": call.id, "status": "uploaded"}


@router.post("/calls/{call_id}/extract")
async def extract_call(
    call_id: str, transcript: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    call = db.get(Call, call_id)
    if not call or (call.agent_id != user.id and user.role.value != "responsable"):
        raise HTTPException(404, "Appel introuvable")
    result = await HybridExtractor(get_settings()).extract(transcript)
    call.transcript = transcript
    call.completed_at = datetime.now(UTC)
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
    db.add(
        AuditLog(
            user_id=user.id,
            action="ai_extraction",
            entity_type="claim",
            entity_id=claim.id,
            details=result.trace,
        )
    )
    db.commit()
    return {"claim_id": claim.id, "call_id": call.id, "extraction": result}


@router.post("/calls/{call_id}/transcribe")
def transcribe_call(
    call_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Transcrit et persiste le transcript sans lancer l'extraction structurée."""
    call = db.get(Call, call_id)
    if not call or (call.agent_id != user.id and user.role.value != "responsable"):
        raise HTTPException(404, "Appel introuvable")
    segments = Transcriber(get_settings()).transcribe(Path(call.audio_reference))
    try:
        turns = Diarizer(get_settings()).diarize(Path(call.audio_reference))
    except RuntimeError:
        turns = []
    labelled = align_and_label(segments, turns)
    call.transcript = "\n".join(f"{item.speaker}: {item.text}" for item in labelled)
    call.segments = [item.model_dump() for item in labelled]
    db.add(
        AuditLog(
            user_id=user.id,
            action="transcription",
            entity_type="call",
            entity_id=call.id,
            details={"segments": len(labelled)},
        )
    )
    db.commit()
    return {"call_id": call.id, "transcript": call.transcript, "segments": labelled}


@router.post("/calls/demo", status_code=201)
async def create_demo_call(
    body: TranscriptRequest, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Parcours de secours sans poids STT : transcript fourni et réellement persisté."""
    result = await HybridExtractor(get_settings()).extract(body.transcript)
    call = Call(
        agent_id=user.id,
        audio_reference="demo://transcript",
        transcript=body.transcript,
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


@router.post("/calls/{call_id}/process")
async def process_call_audio(
    call_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Pipeline GPU complet ; l'endpoint /extract reste le mode démo transcript/offline."""
    call = db.get(Call, call_id)
    if not call or (call.agent_id != user.id and user.role.value != "responsable"):
        raise HTTPException(404, "Appel introuvable")
    result, segments = await process_audio(Path(call.audio_reference), get_settings())
    call.transcript = "\n".join(f"{s.speaker}: {s.text}" for s in segments)
    call.segments = [s.model_dump() for s in segments]
    call.completed_at = datetime.now(UTC)
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
    db.add(
        AuditLog(
            user_id=user.id,
            action="ai_pipeline",
            entity_type="claim",
            entity_id=claim.id,
            details=result.trace,
        )
    )
    db.commit()
    return {"claim_id": claim.id, "segments": segments, "extraction": result}


@router.get("/claims")
def list_claims(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Claim).join(Call).order_by(Claim.created_at.desc())
    if user.role.value == "agent":
        stmt = stmt.where(Call.agent_id == user.id)
    return db.scalars(stmt).all()


@router.put("/claims/{claim_id}")
def update_claim(
    claim_id: str,
    body: ClaimUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Déclaration introuvable")
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
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Déclaration introuvable")
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
    claim = db.get(Claim, claim_id)
    if not claim or claim.status != ClaimStatus.validated or not claim.validated_by:
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
    claim = db.get(Claim, claim_id)
    if not claim or claim.status not in {ClaimStatus.validated, ClaimStatus.sent}:
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
