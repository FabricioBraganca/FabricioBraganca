"""Consultas e persistência do parque de equipamentos."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toner_api.models.enums import PapelNoParque, StatusOperacional, StatusOS, TipoEquipamento
from toner_api.models.equipment import Equipamento
from toner_api.models.work_orders import OrdemServico
from toner_api.repositories.common import paginar


class EquipamentoRepository:
    """Acesso ao inventário, ao grupo EM_USO/BACKUP e às OS vinculadas."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self, equipamento_id: UUID) -> Equipamento | None:
        return self.db.get(Equipamento, equipamento_id)

    def listar(
        self,
        limit: int,
        offset: int,
        tipo: TipoEquipamento | None = None,
        status_operacional: StatusOperacional | None = None,
        papel_no_parque: PapelNoParque | None = None,
        localizacao: str | None = None,
        busca: str | None = None,
    ) -> tuple[list[Equipamento], int]:
        statement = select(Equipamento)
        if tipo is not None:
            statement = statement.where(Equipamento.tipo == tipo)
        if status_operacional is not None:
            statement = statement.where(Equipamento.status_operacional == status_operacional)
        if papel_no_parque is not None:
            statement = statement.where(Equipamento.papel_no_parque == papel_no_parque)
        if localizacao is not None:
            statement = statement.where(Equipamento.localizacao.ilike(f"%{localizacao}%"))
        if busca:
            pattern = f"%{busca}%"
            statement = statement.where(
                Equipamento.patrimonio.ilike(pattern)
                | Equipamento.numero_serie.ilike(pattern)
                | Equipamento.marca.ilike(pattern)
                | Equipamento.modelo.ilike(pattern)
                | Equipamento.localizacao.ilike(pattern)
            )
        return paginar(self.db, statement.order_by(Equipamento.patrimonio, Equipamento.id), limit, offset)

    def equipamentos_em_uso_no_grupo(self, equipamento: Equipamento) -> list[Equipamento]:
        statement = select(Equipamento).where(
            Equipamento.id != equipamento.id,
            Equipamento.localizacao == equipamento.localizacao,
            Equipamento.papel_no_parque == PapelNoParque.EM_USO,
            Equipamento.status_operacional != StatusOperacional.DESCARTADO,
        )
        if equipamento.responsavel_id is None:
            statement = statement.where(Equipamento.responsavel_id.is_(None))
        else:
            statement = statement.where(Equipamento.responsavel_id == equipamento.responsavel_id)
        return list(self.db.scalars(statement.with_for_update()).all())

    def tem_os_aberta(self, equipamento_id: UUID) -> bool:
        open_statuses = {
            StatusOS.ABERTA,
            StatusOS.EM_ANDAMENTO,
            StatusOS.AGUARDANDO_USUARIO,
            StatusOS.AGUARDANDO_PECA,
        }
        return bool(
            self.db.scalar(
                select(func.count())
                .select_from(OrdemServico)
                .where(OrdemServico.equipamento_id == equipamento_id, OrdemServico.status.in_(open_statuses))
            )
        )

    def contar_por_papel(self) -> dict[PapelNoParque, int]:
        totals = self.db.execute(
            select(Equipamento.papel_no_parque, func.count())
            .where(Equipamento.status_operacional != StatusOperacional.DESCARTADO)
            .group_by(Equipamento.papel_no_parque)
        ).all()
        return {papel: total for papel, total in totals}