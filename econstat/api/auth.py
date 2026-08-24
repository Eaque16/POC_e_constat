from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from econstat.config import get_settings
from econstat.database import get_db
from econstat.models import AuditLog, User
from econstat.schemas.auth import TokenResponse
from econstat.services.auth import create_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db.add(
        AuditLog(
            user_id=user.id,
            action="login_success",
            entity_type="user",
            entity_id=user.id,
            details_json={},
        )
    )
    db.commit()
    return TokenResponse(
        access_token=create_token(user.id, user.role.value, get_settings()),
        username=user.username,
        role=user.role.value,
    )
