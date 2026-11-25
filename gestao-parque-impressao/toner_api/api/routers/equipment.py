"""Endpoints de inventário e gestão de equipamentos em uso/backup."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from toner_api.api.dependencies import get_current_user, require_role
from toner_api.core.errors import BusinessRuleError
from toner_api.db.session import get_db
from toner_api.models.enums import PapelNoParque, Perfil, StatusOperacional, TipoEquipamento
from toner_api.models.equipment import Equipamento
from toner_api.models.users import Usuario
from toner_api.schemas.common import Pagina
from toner_api.schemas.equipment import EquipamentoCreate, EquipamentoOut, EquipamentoParqueResumo, EquipamentoUpdate
from toner_api.services.equipment_service import EquipamentoService

router = APIRouter(prefix="/equipamentos", tags=["equipamentos"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]
AdminUser = Annotated[Usuario, Depends(require_role(Perfil.ADMIN))]
AdminOrTech = Annotated[Usuario, Depends(require_role(Perfil.ADMIN, Perfil.TECNICO))]


@router.get("/parque", response_model=EquipamentoParqueResumo)
def park_summary(db: Database, _user: AdminOrTech) -> dict[str, object]:
    return EquipamentoService(db).parque()


@router.get("", response_model=Pagina[EquipamentoOut])
def list_equipment(
    db: Database,
    _user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    tipo: TipoEquipamento | None = None,
    status_operacional: StatusOperacional | None = None,
    papel_no_parque: PapelNoParque | None = None,
    localizacao: str | None = None,
    busca: str | None = None,
) -> Pagina[EquipamentoOut]:
    service = EquipamentoService(db)
    items, total = service.listar(
        limit,
        offset,
        tipo=tipo,
        status_operacional=status_operacional,
        papel_no_parque=papel_no_parque,
        localizacao=localizacao,
        busca=busca,
    )
    return Pagina[EquipamentoOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=EquipamentoOut, status_code=status.HTTP_201_CREATED)
def create_equipment(payload: EquipamentoCreate, db: Database, _admin: AdminUser) -> Equipamento:
    return EquipamentoService(db).criar(payload)


@router.get("/{equipamento_id}", response_model=EquipamentoOut)
def get_equipment(equipamento_id: UUID, db: Database, _user: CurrentUser) -> Equipamento:
    return EquipamentoService(db).obter(equipamento_id)


@router.patch("/{equipamento_id}", response_model=EquipamentoOut)
def update_equipment(
    equipamento_id: UUID,
    payload: EquipamentoUpdate,
    db: Database,
    current_user: CurrentUser,
) -> Equipamento:
    if current_user.perfil == Perfil.TECNICO:
        updates = payload.model_dump(exclude_unset=True)
        if set(updates) != {"status_operacional"} or updates["status_operacional"] is None:
            raise BusinessRuleError("Técnicos só podem alterar o status operacional do equipamento.")
        return EquipamentoService(db).alterar_status(equipamento_id, updates["status_operacional"])
    if current_user.perfil != Perfil.ADMIN:
        raise BusinessRuleError("Perfil sem permissão para atualizar equipamentos.")
    return EquipamentoService(db).atualizar(equipamento_id, payload)


@router.delete("/{equipamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(equipamento_id: UUID, db: Database, _admin: AdminUser) -> Response:
    EquipamentoService(db).excluir(equipamento_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{equipamento_id}/promover-backup", response_model=EquipamentoOut)
def promote_backup(equipamento_id: UUID, db: Database, _user: AdminOrTech) -> Equipamento:
    return EquipamentoService(db).promover_backup(equipamento_id)