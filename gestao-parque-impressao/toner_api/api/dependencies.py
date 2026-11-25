"""Dependências FastAPI para autenticação e autorização por perfil."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from toner_api.db.session import get_db
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.core.security import TokenValidationError, decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """Valida access token e carrega o usuário ativo associado."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não informado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id: UUID = decode_token(credentials.credentials, "access")
    except TokenValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    user = db.scalar(select(Usuario).where(Usuario.id == user_id, Usuario.ativo.is_(True)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inválido ou inativo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed_roles: Perfil) -> Callable[..., Usuario]:
    """Cria dependência que permite acesso apenas aos perfis informados."""
    if not allowed_roles:
        raise ValueError("Informe ao menos um perfil autorizado.")

    def authorize(current_user: Annotated[Usuario, Depends(get_current_user)]) -> Usuario:
        if current_user.perfil not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")
        return current_user

    return authorize