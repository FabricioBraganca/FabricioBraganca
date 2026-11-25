"""Endpoints administrativos de parâmetros de SLA e calendário."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from toner_api.api.dependencies import require_role
from toner_api.db.session import get_db
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.schemas.common import Pagina
from toner_api.schemas.config import (
    FeriadoCreate,
    FeriadoOut,
    HorarioFuncionamentoCreate,
    HorarioFuncionamentoOut,
    SlaConfigOut,
    SlaConfigUpdate,
)
from toner_api.services.config_service import ConfiguracaoService

router = APIRouter(tags=["configuração"])
Database = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[Usuario, Depends(require_role(Perfil.ADMIN))]


@router.get("/sla-config", response_model=Pagina[SlaConfigOut])
def list_sla_config(
    db: Database,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[SlaConfigOut]:
    configs = ConfiguracaoService(db).listar_sla()
    return Pagina[SlaConfigOut](items=configs[offset : offset + limit], total=len(configs), limit=limit, offset=offset)


@router.put("/sla-config", response_model=list[SlaConfigOut])
def update_sla_config(payload: list[SlaConfigUpdate], db: Database, _admin: AdminUser) -> list[SlaConfigOut]:
    return ConfiguracaoService(db).atualizar_sla(payload)


@router.get("/horarios-funcionamento", response_model=Pagina[HorarioFuncionamentoOut])
def list_working_hours(
    db: Database,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[HorarioFuncionamentoOut]:
    items, total = ConfiguracaoService(db).listar_horarios(limit, offset)
    return Pagina[HorarioFuncionamentoOut](items=items, total=total, limit=limit, offset=offset)


@router.post("/horarios-funcionamento", response_model=HorarioFuncionamentoOut, status_code=status.HTTP_201_CREATED)
def create_working_hours(
    payload: HorarioFuncionamentoCreate, db: Database, _admin: AdminUser
) -> HorarioFuncionamentoOut:
    return ConfiguracaoService(db).criar_horario(payload)


@router.get("/feriados", response_model=Pagina[FeriadoOut])
def list_holidays(
    db: Database,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[FeriadoOut]:
    items, total = ConfiguracaoService(db).listar_feriados(limit, offset)
    return Pagina[FeriadoOut](items=items, total=total, limit=limit, offset=offset)


@router.post("/feriados", response_model=FeriadoOut, status_code=status.HTTP_201_CREATED)
def create_holiday(payload: FeriadoCreate, db: Database, _admin: AdminUser) -> FeriadoOut:
    return ConfiguracaoService(db).criar_feriado(payload)