"""Consultas e persistência de ordens de serviço e auditoria."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toner_api.models.enums import Prioridade, StatusOS
from toner_api.models.work_orders import HistoricoOS, OrdemServico
from toner_api.repositories.common import paginar


class OrdemServicoRepository:
    """Acesso a OS com filtros, escopo do solicitante e histórico imutável."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self, os_id: UUID) -> OrdemServico | None:
        return self.db.get(OrdemServico, os_id)

    def obter_do_solicitante(self, os_id: UUID, solicitante_id: UUID) -> OrdemServico | None:
        return self.db.scalar(
            select(OrdemServico).where(
                OrdemServico.id == os_id,
                OrdemServico.solicitante_id == solicitante_id,
            )
        )

    def listar(
        self,
        limit: int,
        offset: int,
        status: StatusOS | None = None,
        prioridade: Prioridade | None = None,
        tecnico_id: UUID | None = None,
        equipamento_id: UUID | None = None,
        solicitante_id: UUID | None = None,
        inicio: datetime | None = None,
        fim: datetime | None = None,
    ) -> tuple[list[OrdemServico], int]:
        statement = select(OrdemServico)
        if status is not None:
            statement = statement.where(OrdemServico.status == status)
        if prioridade is not None:
            statement = statement.where(OrdemServico.prioridade == prioridade)
        if tecnico_id is not None:
            statement = statement.where(OrdemServico.tecnico_id == tecnico_id)
        if equipamento_id is not None:
            statement = statement.where(OrdemServico.equipamento_id == equipamento_id)
        if solicitante_id is not None:
            statement = statement.where(OrdemServico.solicitante_id == solicitante_id)
        if inicio is not None:
            statement = statement.where(OrdemServico.aberta_em >= inicio)
        if fim is not None:
            statement = statement.where(OrdemServico.aberta_em <= fim)
        statement = statement.order_by(OrdemServico.aberta_em.desc(), OrdemServico.id)
        return paginar(self.db, statement, limit, offset)

    def historico(self, os_id: UUID) -> list[HistoricoOS]:
        return list(
            self.db.scalars(
                select(HistoricoOS).where(HistoricoOS.os_id == os_id).order_by(HistoricoOS.criado_em, HistoricoOS.id)
            ).all()
        )

    def contar_por_status(self) -> dict[StatusOS, int]:
        rows = self.db.execute(select(OrdemServico.status, func.count()).group_by(OrdemServico.status)).all()
        return {status: total for status, total in rows}

    def adicionar(self, os: OrdemServico) -> OrdemServico:
        self.db.add(os)
        self.db.flush()
        return os

    def adicionar_historico(self, historico: HistoricoOS) -> HistoricoOS:
        self.db.add(historico)
        self.db.flush()
        return historico