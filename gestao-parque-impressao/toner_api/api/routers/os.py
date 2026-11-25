"""Endpoints de ordens de serviço, histórico e dashboard."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from toner_api.api.dependencies import get_current_user, require_role
from toner_api.db.session import get_db
from toner_api.models.enums import Perfil, Prioridade, StatusOS, StatusSLA
from toner_api.models.users import Usuario
from toner_api.schemas.common import Pagina
from toner_api.schemas.os import (
    AtribuicaoTecnico,
    DashboardOS,
    HistoricoOSOut,
    OrdemServicoCreate,
    OrdemServicoOut,
    OrdemServicoUpdate,
    TransicaoStatusOS,
)
from toner_api.services.os_service import OrdemServicoService

router = APIRouter(prefix="/os", tags=["ordens de serviço"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]
AdminOrTech = Annotated[Usuario, Depends(require_role(Perfil.ADMIN, Perfil.TECNICO))]
AdminUser = Annotated[Usuario, Depends(require_role(Perfil.ADMIN))]


@router.get("/dashboard", response_model=DashboardOS)
def os_dashboard(db: Database, user: AdminOrTech) -> DashboardOS:
    return OrdemServicoService(db).dashboard(user)


@router.get("", response_model=Pagina[OrdemServicoOut])
def list_work_orders(
    db: Database,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_os: StatusOS | None = Query(default=None, alias="status"),
    prioridade: Prioridade | None = None,
    tecnico_id: UUID | None = None,
    equipamento_id: UUID | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    sla_status: StatusSLA | None = None,
) -> Pagina[OrdemServicoOut]:
    items, total = OrdemServicoService(db).listar(
        current_user,
        limit,
        offset,
        status_os,
        prioridade,
        tecnico_id,
        equipamento_id,
        inicio,
        fim,
        sla_status,
    )
    return Pagina[OrdemServicoOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=OrdemServicoOut, status_code=status.HTTP_201_CREATED)
def create_work_order(payload: OrdemServicoCreate, db: Database, current_user: CurrentUser) -> OrdemServicoOut:
    return OrdemServicoService(db).criar(payload, current_user)


@router.get("/{os_id}/historico", response_model=Pagina[HistoricoOSOut])
def work_order_history(
    os_id: UUID,
    db: Database,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[HistoricoOSOut]:
    history = OrdemServicoService(db).historico(os_id, current_user)
    return Pagina[HistoricoOSOut](items=history[offset : offset + limit], total=len(history), limit=limit, offset=offset)


@router.patch("/{os_id}/status", response_model=OrdemServicoOut)
def transition_work_order(
    os_id: UUID, payload: TransicaoStatusOS, db: Database, current_user: AdminOrTech
) -> OrdemServicoOut:
    return OrdemServicoService(db).transicionar(
        os_id,
        current_user,
        payload.status,
        payload.solucao_aplicada,
        payload.observacao,
    )


@router.patch("/{os_id}/atribuir-tecnico", response_model=OrdemServicoOut)
def assign_technician(
    os_id: UUID, payload: AtribuicaoTecnico, db: Database, current_user: AdminUser
) -> OrdemServicoOut:
    return OrdemServicoService(db).atribuir_tecnico(os_id, current_user, payload.tecnico_id)


@router.get("/{os_id}", response_model=OrdemServicoOut)
def get_work_order(os_id: UUID, db: Database, current_user: CurrentUser) -> OrdemServicoOut:
    return OrdemServicoService(db).obter(os_id, current_user)


@router.patch("/{os_id}", response_model=OrdemServicoOut)
def update_work_order(
    os_id: UUID, payload: OrdemServicoUpdate, db: Database, current_user: CurrentUser
) -> OrdemServicoOut:
    return OrdemServicoService(db).atualizar(os_id, current_user, payload)