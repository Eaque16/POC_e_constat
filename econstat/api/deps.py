from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from econstat.config import get_settings
from econstat.database import get_db
from econstat.models import Role, User
from econstat.services.auth import decode_token

security = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    if settings.disable_auth:
        user = db.query(User).filter(User.username == "agent.demo").first()
        if not user:
            raise HTTPException(503, "Compte agent.demo non initialisé")
        return user
    try:
        if credentials is None:
            raise ValueError("Jeton absent")
        payload = decode_token(credentials.credentials, settings)
        user = db.get(User, payload["sub"])
    except Exception as exc:
        raise HTTPException(401, "Jeton invalide ou expiré") from exc
    if not user:
        raise HTTPException(401, "Utilisateur inconnu")
    return user


def responsable(user: User = Depends(current_user)) -> User:
    if get_settings().disable_auth:
        return user
    if user.role != Role.responsable:
        raise HTTPException(403, "Rôle responsable requis")
    return user
