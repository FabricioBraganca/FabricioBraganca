"""Endpoints administrativos de gestão de usuários."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from toner_api.api.dependencies import require_role
from toner_api.db.session import get_db
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.schemas.common import Pagina
from toner_api.schemas.users import UsuarioCreate, UsuarioOut, UsuarioUpdate
from toner_api.services.user_service import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["usuários"])
Database = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[Usuario, Depends(require_role(Perfil.ADMIN))]


@router.get("", response_model=Pagina[UsuarioOut])
def list_users(
    db: Database,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    perfil: Perfil | None = None,
    setor: str | None = None,
    ativo: bool | None = None,
) -> Pagina[UsuarioOut]:
    items, total = UsuarioService(db).listar(limit, offset, perfil, setor, ativo)
    return Pagina[UsuarioOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UsuarioCreate, db: Database, _admin: AdminUser) -> Usuario:
    return UsuarioService(db).criar(payload)


@router.get("/{usuario_id}", response_model=UsuarioOut)
def get_user(usuario_id: UUID, db: Database, _admin: AdminUser) -> Usuario:
    return UsuarioService(db).obter(usuario_id)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def update_user(usuario_id: UUID, payload: UsuarioUpdate, db: Database, _admin: AdminUser) -> Usuario:
    return UsuarioService(db).atualizar(usuario_id, payload)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(usuario_id: UUID, db: Database, _admin: AdminUser) -> Response:
    UsuarioService(db).desativar(usuario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)