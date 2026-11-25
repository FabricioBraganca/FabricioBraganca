"""Endpoints de login, renovação de tokens e usuário autenticado."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from toner_api.api.dependencies import get_current_user
from toner_api.db.session import get_db
from toner_api.models.users import Usuario
from toner_api.schemas.users import LoginRequest, RefreshRequest, TokenPair, UsuarioOut
from toner_api.services.user_service import UsuarioService

router = APIRouter(prefix="/auth", tags=["autenticação"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Database) -> TokenPair:
    return UsuarioService(db).autenticar(str(payload.email), payload.senha)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Database) -> TokenPair:
    return UsuarioService(db).renovar_tokens(payload.refresh_token)


@router.get("/me", response_model=UsuarioOut)
def me(current_user: CurrentUser) -> Usuario:
    return current_user