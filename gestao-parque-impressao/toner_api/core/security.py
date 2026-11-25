"""Hash de senhas e emissão/validação de tokens JWT."""

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from toner_api.core.config import get_settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenValidationError(ValueError):
    """Indica que um token está inválido, expirado ou é do tipo incorreto."""


def hash_password(password: str) -> str:
    """Gera hash bcrypt sem truncar silenciosamente senhas longas."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("A senha não pode exceder 72 bytes no algoritmo bcrypt.")
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Compara uma senha em texto com seu hash bcrypt."""
    return password_context.verify(password, password_hash)


def _create_token(subject: UUID, token_type: str, expires_at: datetime) -> str:
    """Cria um JWT com identificador do usuário, tipo e expiração explícitos."""
    settings = get_settings()
    claims: dict[str, object] = {
        "sub": str(subject),
        "type": token_type,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: UUID) -> str:
    """Cria access token com o prazo de expiração configurado."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=get_settings().access_token_expire_minutes)
    return _create_token(subject, "access", expires_at)


def create_refresh_token(subject: UUID) -> str:
    """Cria refresh token com o prazo de expiração configurado."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days)
    return _create_token(subject, "refresh", expires_at)


def decode_token(token: str, expected_type: str) -> UUID:
    """Valida assinatura, expiração e tipo do token e retorna o UUID do usuário."""
    settings = get_settings()
    try:
        decoded = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as error:
        raise TokenValidationError("Token inválido ou expirado.") from error

    claims = cast(dict[str, object], decoded)
    subject = claims.get("sub")
    if claims.get("type") != expected_type or not isinstance(subject, str):
        raise TokenValidationError("Tipo de token ou identificador inválido.")
    try:
        return UUID(subject)
    except ValueError as error:
        raise TokenValidationError("Identificador de usuário inválido no token.") from error