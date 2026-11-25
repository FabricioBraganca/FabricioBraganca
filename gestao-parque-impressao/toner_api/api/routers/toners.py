"""Endpoints de catálogo e controle FIFO de estoque de toner."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from toner_api.api.dependencies import require_role
from toner_api.db.session import get_db
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.schemas.common import Pagina
from toner_api.schemas.toners import (
    ConsumoToner,
    ConsumoTonerOut,
    FilaFIFOItem,
    LoteTonerCreate,
    LoteTonerOut,
    MovimentacaoTonerOut,
    TonerCreate,
    TonerOut,
    TonerUpdate,
)
from toner_api.services.toner_service import TonerService

router = APIRouter(prefix="/toners", tags=["toners"])
Database = Annotated[Session, Depends(get_db)]
AdminOrTech = Annotated[Usuario, Depends(require_role(Perfil.ADMIN, Perfil.TECNICO))]
AdminUser = Annotated[Usuario, Depends(require_role(Perfil.ADMIN))]


@router.get("/estoque-critico", response_model=Pagina[TonerOut])
def critical_stock(
    db: Database,
    _user: AdminOrTech,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[TonerOut]:
    items, total = TonerService(db).estoque_critico(limit, offset)
    return Pagina[TonerOut](items=items, total=total, limit=limit, offset=offset)


@router.get("", response_model=Pagina[TonerOut])
def list_toners(
    db: Database,
    _user: AdminOrTech,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    busca: str | None = None,
) -> Pagina[TonerOut]:
    items, total = TonerService(db).listar(limit, offset, busca)
    return Pagina[TonerOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=TonerOut, status_code=status.HTTP_201_CREATED)
def create_toner(payload: TonerCreate, db: Database, _admin: AdminUser) -> TonerOut:
    return TonerService(db).criar(payload)


@router.get("/{toner_id}", response_model=TonerOut)
def get_toner(toner_id: UUID, db: Database, _user: AdminOrTech) -> TonerOut:
    return TonerService(db).obter(toner_id)


@router.patch("/{toner_id}", response_model=TonerOut)
def update_toner(toner_id: UUID, payload: TonerUpdate, db: Database, _admin: AdminUser) -> TonerOut:
    return TonerService(db).atualizar(toner_id, payload)


@router.post("/{toner_id}/lotes", response_model=LoteTonerOut, status_code=status.HTTP_201_CREATED)
def receive_toner_lot(
    toner_id: UUID, payload: LoteTonerCreate, db: Database, current_user: AdminOrTech
) -> LoteTonerOut:
    return LoteTonerOut.model_validate(TonerService(db).entrada(toner_id, payload, current_user))


@router.post("/{toner_id}/consumir", response_model=ConsumoTonerOut)
def consume_toner(
    toner_id: UUID, payload: ConsumoToner, db: Database, current_user: AdminOrTech
) -> ConsumoTonerOut:
    movements = TonerService(db).consumir(
        toner_id,
        payload.quantidade,
        current_user,
        payload.os_id,
        payload.observacao,
    )
    return ConsumoTonerOut(
        quantidade=payload.quantidade,
        movimentacoes=[MovimentacaoTonerOut.model_validate(movement) for movement in movements],
    )


@router.get("/{toner_id}/fifo", response_model=Pagina[FilaFIFOItem])
def fifo_queue(
    toner_id: UUID,
    db: Database,
    _user: AdminOrTech,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[FilaFIFOItem]:
    queue = TonerService(db).fila_fifo(toner_id)
    return Pagina[FilaFIFOItem](items=queue[offset : offset + limit], total=len(queue), limit=limit, offset=offset)


@router.get("/{toner_id}/movimentacoes", response_model=Pagina[MovimentacaoTonerOut])
def toner_movements(
    toner_id: UUID,
    db: Database,
    _user: AdminOrTech,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[MovimentacaoTonerOut]:
    items, total = TonerService(db).movimentacoes(toner_id, limit, offset)
    return Pagina[MovimentacaoTonerOut](items=items, total=total, limit=limit, offset=offset)