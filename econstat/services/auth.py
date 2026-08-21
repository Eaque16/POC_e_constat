from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from econstat.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user_id: str, role: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "role": role,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
