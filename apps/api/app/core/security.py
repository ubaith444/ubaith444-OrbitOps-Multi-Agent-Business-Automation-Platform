from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_token(subject: UUID, tenant_id: UUID, role: str, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == TokenType.ACCESS
        else timedelta(days=settings.refresh_token_days)
    )
    claims = {
        "sub": str(subject),
        "tenant": str(tenant_id),
        "role": role,
        "type": token_type.value,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(claims, settings.app_secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected: TokenType = TokenType.ACCESS) -> dict[str, str]:
    claims = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
    if claims.get("type") != expected.value:
        raise jwt.InvalidTokenError("Unexpected token type")
    return claims
