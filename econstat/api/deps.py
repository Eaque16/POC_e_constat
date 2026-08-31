from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from econstat.config import get_settings
from econstat.database import get_db
from econstat.models import Call, Claim, ProcessingJob, Role, User
from econstat.services.auth import decode_token

security = HTTPBearer(auto_error=False)


def unauthorized(detail: str = "Authentification requise") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    if settings.disable_auth and credentials is None:
        user = db.query(User).filter(User.username == "agent.demo").first()
        if not user:
            raise unauthorized("Mode démo demandé mais compte agent.demo non initialisé")
        return user
    try:
        if credentials is None:
            raise unauthorized()
        payload = decode_token(credentials.credentials, settings)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise unauthorized("Jeton sans sujet valide")
        user = db.get(User, subject)
    except HTTPException:
        raise
    except Exception as exc:
        raise unauthorized("Jeton invalide ou expiré") from exc
    if not user:
        raise unauthorized("Utilisateur inconnu")
    return user


def responsable(user: User = Depends(current_user)) -> User:
    # Le mode de démonstration local n'affiche pas d'écran de connexion : il doit
    # pouvoir présenter le dashboard global. Cette exception ne s'applique jamais
    # lorsque l'authentification est active.
    if get_settings().disable_auth:
        return user
    if user.role != Role.responsable:
        raise HTTPException(403, "Rôle responsable requis")
    return user


def user_can_access_owner(user: User, owner_id: str) -> bool:
    return user.role == Role.responsable or owner_id == user.id


def get_owned_call_or_404(call_id: str, user: User, db: Session) -> Call:
    call = db.get(Call, call_id)
    if not call or not user_can_access_owner(user, call.owner_id):
        raise HTTPException(404, "Appel introuvable")
    return call


def get_owned_claim_or_404(claim_id: str, user: User, db: Session) -> Claim:
    claim = db.scalar(
        select(Claim).join(Call, Claim.call_id == Call.id).where(Claim.id == claim_id)
    )
    if not claim or not user_can_access_owner(user, claim.call.owner_id):
        raise HTTPException(404, "Déclaration introuvable")
    return claim


def get_owned_job_or_404(job_id: str, user: User, db: Session) -> ProcessingJob:
    job = db.scalar(
        select(ProcessingJob)
        .join(Call, ProcessingJob.call_id == Call.id)
        .where(ProcessingJob.id == job_id)
    )
    if not job or not user_can_access_owner(user, job.call.owner_id):
        raise HTTPException(404, "Traitement introuvable")
    return job
