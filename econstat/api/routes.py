import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
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
from econstat.schemas.call import (
    CallReviewResponse,
    CallUploadResponse,
    SpeakerCorrectionsRequest,
    SpeakerCorrectionsResponse,
)
from econstat.schemas.claim import (
    QUESTION_TEMPLATES,
    REQUIRED_FIELDS,
    ClaimData,
    ClaimReviewResponse,
    TranscriptSegment,
)
from econstat.schemas.dashboard import DashboardResponse
from econstat.schemas.job import JobResponse
from econstat.services.audio_validation import AudioValidationError, validate_and_store_audio
from econstat.services.dashboard import build_dashboard
from econstat.services.econsta import EConstaClient, EConstaError, EConstaTimeoutError
from econstat.services.extraction import HybridExtractor
from econstat.services.jobs import create_job
from econstat.services.json_export import generate_claim_json
from econstat.services.realtime_transcription import get_realtime_transcriber
from econstat.services.transcription import TranscriptionError
from econstat.services.conversation import WELCOME_MESSAGE, new_conversation, progress, respond

router = APIRouter()


@router.post("/transcription/chunk")
async def transcribe_live_chunk(
    request: Request,
    _: User = Depends(current_user),
):
    """Transcrit un segment WebM court envoyé par le frontend React."""
    audio = await request.body()
    if not audio:
        raise HTTPException(422, "Segment audio vide.")
    if len(audio) > 10 * 1024 * 1024:
        raise HTTPException(413, "Segment audio trop volumineux.")
    settings = get_settings()
    chunk_dir = settings.recordings_dir / ".stream"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"{uuid.uuid4()}.webm"
    chunk_path.write_bytes(audio)
    try:
        result = get_realtime_transcriber(settings, "precision").transcribe(chunk_path)
    except TranscriptionError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        chunk_path.unlink(missing_ok=True)
    return {
        "speaker": "assure",
        "text": result.text,
        "confidence": result.confidence,
    }


class ClaimUpdate(BaseModel):
    data: ClaimData


class TranscriptRequest(BaseModel):
    transcript: str


class ConversationClaimRequest(BaseModel):
    data: ClaimData
    transcript: list[str]
    claim_id: str | None = None
    field_records: dict[str, dict] = Field(default_factory=dict)


class ConversationTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    state: dict
    asr_confidence: float = Field(default=0.75, ge=0, le=1)


@router.post("/conversations/start")
def start_guided_conversation(_: User = Depends(current_user)):
    """Démarre le moteur conversationnel réel utilisé par les interfaces clientes."""
    state = new_conversation()
    return {
        "reply": WELCOME_MESSAGE,
        "state": state,
        "progress": progress(state["data"]),
        "complete": False,
    }


@router.post("/conversations/respond")
def respond_to_guided_conversation(
    body: ConversationTurnRequest,
    _: User = Depends(current_user),
):
    """Parse une réponse client dans le slot attendu et retourne la prochaine question."""
    reply, state = respond(
        body.message,
        body.state,
        asr_confidence=body.asr_confidence,
    )
    return {
        "reply": reply,
        "state": state,
        "progress": progress(state.get("data", {})),
        "complete": state.get("current_field") is None,
    }


def claim_review_response(claim: Claim) -> ClaimReviewResponse:
    trace = claim.model_trace_json or {}
    proposed = trace.get("ai_proposal", claim.data_json or {})
    return ClaimReviewResponse(
        id=claim.id,
        call_id=claim.call_id,
        status=claim.status.value,
        proposed_data=proposed,
        current_data=claim.data_json or {},
        validated_data=(claim.data_json or {})
        if claim.status in {ClaimStatus.validated, ClaimStatus.sent}
        else None,
        confidence=claim.confidence_json or {},
        evidence=claim.evidence_json or {},
        missing_fields=claim.missing_fields_json or [],
        questions=claim.questions_json or [],
        global_confidence=claim.global_confidence,
        human_corrections=claim.human_corrections,
        validated_by=claim.validated_by,
        validated_at=claim.validated_at,
        external_id=claim.external_id,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


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


@router.get("/calls/{call_id}", response_model=CallReviewResponse)
def get_call(
    call_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> CallReviewResponse:
    call = get_owned_call_or_404(call_id, user, db)
    return CallReviewResponse(
        id=call.id,
        duration_seconds=call.duration_seconds,
        transcript_text=call.transcript_text,
        segments=[TranscriptSegment.model_validate(item) for item in (call.segments_json or [])],
        created_at=call.created_at,
        completed_at=call.completed_at,
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
        evidence_json=result.evidence,
        missing_fields=result.missing_fields,
        suggested_questions=result.suggested_questions,
        confidence_score=result.overall_confidence,
        model_trace={**result.trace, "ai_proposal": result.data.model_dump(mode="json")},
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


@router.post("/conversations/claims", status_code=201)
def create_conversation_claim(
    body: ConversationClaimRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Transforme une conversation guidée en dossier soumis au contrôle humain."""
    data = body.data.model_dump(mode="json")
    missing = [field for field in REQUIRED_FIELDS if data.get(field) is None]
    transcript = "\n".join(line.strip() for line in body.transcript if line.strip())
    confidence = {field: 1.0 for field, value in data.items() if value is not None}
    if body.claim_id:
        claim = get_owned_claim_or_404(body.claim_id, user, db)
        call = claim.call
        call.transcript_text = transcript
        claim.data_json = data
        claim.confidence_json = confidence
        claim.missing_fields_json = missing
        claim.questions_json = [QUESTION_TEMPLATES[field] for field in missing]
        claim.global_confidence = len(confidence) / len(REQUIRED_FIELDS)
        claim.model_trace_json = {
            **(claim.model_trace_json or {}),
            "source": "guided_conversation",
            "field_records": body.field_records,
        }
        action = "conversation_claim_updated"
    else:
        call = Call(
            owner_id=user.id,
            audio_path="conversation://chat",
            transcript_text=transcript,
            segments_json=[],
            completed_at=datetime.now(UTC),
        )
        db.add(call)
        db.flush()
        claim = Claim(
            call_id=call.id,
            data_json=data,
            confidence_json=confidence,
            evidence_json={},
            missing_fields_json=missing,
            questions_json=[QUESTION_TEMPLATES[field] for field in missing],
            global_confidence=len(confidence) / len(REQUIRED_FIELDS),
            model_trace_json={
                "source": "guided_conversation",
                "ai_proposal": data,
                "field_records": body.field_records,
            },
            status=ClaimStatus.pending_validation,
        )
        db.add(claim)
        db.flush()
        action = "conversation_claim_created"
    db.add(
        AuditLog(
            user_id=user.id,
            action=action,
            entity_type="claim",
            entity_id=claim.id,
            details_json={"missing_fields": missing},
        )
    )
    db.commit()
    return {"claim_id": claim.id, "call_id": call.id, "missing_fields": missing}


@router.put("/calls/{call_id}/speakers", response_model=SpeakerCorrectionsResponse)
def correct_speaker_roles(
    call_id: str,
    body: SpeakerCorrectionsRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    call = get_owned_call_or_404(call_id, user, db)
    active_job = db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.call_id == call.id)
        .order_by(ProcessingJob.updated_at.desc())
    )
    if active_job is not None and active_job.status != ProcessingJobStatus.ready_for_review:
        raise HTTPException(409, "Les rôles ne peuvent être corrigés qu’après le traitement.")
    segments = [TranscriptSegment.model_validate(item) for item in call.segments_json]
    indexes = [correction.segment_index for correction in body.corrections]
    if len(indexes) != len(set(indexes)):
        raise HTTPException(422, "Un segment ne peut être corrigé qu’une fois par requête.")
    if not segments or any(index >= len(segments) for index in indexes):
        raise HTTPException(422, "Indice de segment invalide.")
    for correction in body.corrections:
        segments[correction.segment_index] = segments[correction.segment_index].model_copy(
            update={"speaker": correction.speaker}
        )
    call.segments_json = [segment.model_dump(mode="json") for segment in segments]
    call.transcript_text = "\n".join(f"{segment.speaker}: {segment.text}" for segment in segments)
    db.add(
        AuditLog(
            user_id=user.id,
            action="speaker_roles_corrected",
            entity_type="call",
            entity_id=call.id,
            details_json={"segment_indexes": indexes, "count": len(indexes)},
        )
    )
    db.commit()
    return SpeakerCorrectionsResponse(
        call_id=call.id,
        corrected_segments=len(indexes),
        segments=segments,
    )


@router.get("/claims", response_model=list[ClaimReviewResponse])
def list_claims(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Claim).join(Call).order_by(Claim.created_at.desc())
    if user.role.value == "agent":
        stmt = stmt.where(Call.owner_id == user.id)
    return [claim_review_response(claim) for claim in db.scalars(stmt).all()]


@router.get("/claims/{claim_id}", response_model=ClaimReviewResponse)
def get_claim(
    claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ClaimReviewResponse:
    return claim_review_response(get_owned_claim_or_404(claim_id, user, db))


@router.put("/claims/{claim_id}")
def update_claim(
    claim_id: str,
    body: ClaimUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    claim = get_owned_claim_or_404(claim_id, user, db)
    if claim.status in {ClaimStatus.validated, ClaimStatus.sent}:
        raise HTTPException(409, "Une déclaration validée ne peut plus être corrigée.")
    trace = dict(claim.model_trace_json or {})
    trace.setdefault("ai_proposal", claim.data_json or {})
    claim.model_trace_json = trace
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
    return claim_review_response(claim)


@router.post("/claims/{claim_id}/validate")
def validate_claim(
    claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    claim = get_owned_claim_or_404(claim_id, user, db)
    if claim.status != ClaimStatus.pending_validation:
        raise HTTPException(409, "Seule une déclaration en attente peut être validée.")
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
    if claim.status == ClaimStatus.sent and claim.external_id:
        db.add(
            AuditLog(
                user_id=user.id,
                action="econsta_idempotent_replay",
                entity_type="claim",
                entity_id=claim.id,
                details_json={"external_id": claim.external_id},
            )
        )
        db.commit()
        return {
            "id": claim.external_id,
            "statut": "deja_envoye",
            "idempotent_replay": True,
        }
    if claim.status != ClaimStatus.validated or not claim.validated_by:
        raise HTTPException(409, "Une validation humaine explicite est obligatoire")
    correlation_id = str(uuid.uuid4())
    db.add(
        AuditLog(
            user_id=user.id,
            action="econsta_send_attempted",
            entity_type="claim",
            entity_id=claim.id,
            details_json={"correlation_id": correlation_id},
        )
    )
    db.commit()
    try:
        result = await EConstaClient(get_settings()).create_claim(
            claim.id,
            claim.data,
            True,
            correlation_id=correlation_id,
        )
    except (EConstaTimeoutError, EConstaError) as exc:
        db.add(
            AuditLog(
                user_id=user.id,
                action="econsta_send_failed",
                entity_type="claim",
                entity_id=claim.id,
                details_json={
                    "correlation_id": correlation_id,
                    "error_type": type(exc).__name__,
                },
            )
        )
        db.commit()
        status_code = 504 if isinstance(exc, EConstaTimeoutError) else 502
        raise HTTPException(status_code, str(exc)) from exc
    claim.external_id = result["id"]
    claim.status = ClaimStatus.sent
    db.add(
        AuditLog(
            user_id=user.id,
            action="sent_to_econsta",
            entity_type="claim",
            entity_id=claim.id,
            details={
                "external_id": claim.external_id,
                "correlation_id": correlation_id,
            },
        )
    )
    db.commit()
    return result


@router.get("/claims/{claim_id}/export-json")
def claim_json_export(
    claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    claim = get_owned_claim_or_404(claim_id, user, db)
    if claim.status not in {ClaimStatus.validated, ClaimStatus.sent}:
        raise HTTPException(409, "L’export JSON exige une validation humaine")
    path = generate_claim_json(
        claim.id,
        claim.data,
        get_settings().generated_dir,
        validated_by=claim.validated_by,
        validated_at=claim.validated_at,
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="json_export_generated",
            entity_type="claim",
            entity_id=claim.id,
            details_json={},
        )
    )
    db.commit()
    return {"path": str(path)}


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(_: User = Depends(responsable), db: Session = Depends(get_db)) -> DashboardResponse:
    return build_dashboard(db)
