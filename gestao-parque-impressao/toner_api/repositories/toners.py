"""Consultas de catálogo, lotes FIFO e trilha de movimentações."""

from uuid import UUID

from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from toner_api.models.toners import LoteToner, MovimentacaoToner, Toner
from toner_api.repositories.common import paginar


class TonerRepository:
    """Acesso a toners, saldo agregado, lotes e movimentações de auditoria."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self, toner_id: UUID) -> Toner | None:
        return self.db.get(Toner, toner_id)

    def listar(self, limit: int, offset: int, busca: str | None = None) -> tuple[list[Toner], int]:
        statement = select(Toner)
        if busca:
            pattern = f"%{busca}%"
            statement = statement.where(Toner.modelo.ilike(pattern) | Toner.compatibilidade.cast(String).ilike(pattern))
        return paginar(self.db, statement.order_by(Toner.modelo, Toner.id), limit, offset)

    def lotes_fifo(self, toner_id: UUID, bloquear: bool = False) -> list[LoteToner]:
        statement = (
            select(LoteToner)
            .where(LoteToner.toner_id == toner_id, LoteToner.ativo.is_(True), LoteToner.quantidade_atual > 0)
            .order_by(LoteToner.data_entrada, LoteToner.id)
        )
        if bloquear:
            statement = statement.with_for_update()
        return list(self.db.scalars(statement).all())

    def saldo(self, toner_id: UUID) -> int:
        return self.db.scalar(
            select(func.coalesce(func.sum(LoteToner.quantidade_atual), 0)).where(
                LoteToner.toner_id == toner_id,
                LoteToner.ativo.is_(True),
            )
        ) or 0

    def movimentacoes(self, toner_id: UUID, limit: int, offset: int) -> tuple[list[MovimentacaoToner], int]:
        statement = select(MovimentacaoToner).where(MovimentacaoToner.toner_id == toner_id)
        return paginar(
            self.db,
            statement.order_by(MovimentacaoToner.criado_em.desc(), MovimentacaoToner.id),
            limit,
            offset,
        )

    def adicionar(self, toner: Toner) -> Toner:
        self.db.add(toner)
        self.db.flush()
        return toner