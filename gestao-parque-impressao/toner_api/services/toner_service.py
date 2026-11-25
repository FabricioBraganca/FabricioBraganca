"""Casos de uso de catálogo, entradas, fila FIFO e movimentações de toner."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from toner_api.core.errors import BusinessRuleError, NotFoundError
from toner_api.models.enums import TipoMovimentacao
from toner_api.models.toners import LoteToner, MovimentacaoToner, Toner
from toner_api.models.users import Usuario
from toner_api.repositories.toners import TonerRepository
from toner_api.schemas.toners import (
    FilaFIFOItem,
    LoteTonerCreate,
    MovimentacaoTonerOut,
    TonerCreate,
    TonerOut,
    TonerUpdate,
)
from toner_api.services.toner_fifo_service import consumir_fifo


class TonerService:
    """Coordena catálogo, saldo agregado e auditoria imutável do estoque."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TonerRepository(db)

    def _para_resposta(self, toner: Toner) -> TonerOut:
        stock = self.repository.saldo(toner.id)
        return TonerOut.model_validate(
            {
                **{column.key: getattr(toner, column.key) for column in Toner.__table__.columns},
                "estoque_atual": stock,
                "abaixo_minimo": stock < toner.estoque_minimo,
            }
        )

    def criar(self, payload: TonerCreate) -> TonerOut:
        toner = self.repository.adicionar(Toner(**payload.model_dump()))
        return self._para_resposta(toner)

    def obter(self, toner_id: UUID) -> TonerOut:
        toner = self.repository.obter(toner_id)
        if toner is None:
            raise NotFoundError("Toner não encontrado.")
        return self._para_resposta(toner)

    def listar(
        self, limit: int, offset: int, busca: str | None = None
    ) -> tuple[list[TonerOut], int]:
        toners, total = self.repository.listar(limit, offset, busca)
        return [self._para_resposta(toner) for toner in toners], total

    def atualizar(self, toner_id: UUID, payload: TonerUpdate) -> TonerOut:
        toner = self.repository.obter(toner_id)
        if toner is None:
            raise NotFoundError("Toner não encontrado.")
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise BusinessRuleError("Informe ao menos um campo para atualizar.")
        for field, value in changes.items():
            setattr(toner, field, value)
        self.db.flush()
        return self._para_resposta(toner)

    def entrada(self, toner_id: UUID, payload: LoteTonerCreate, usuario: Usuario) -> LoteToner:
        """Cria lote independente e registra a entrada correspondente."""
        toner = self.repository.obter(toner_id)
        if toner is None:
            raise NotFoundError("Toner não encontrado.")
        if not toner.ativo:
            raise BusinessRuleError("Não é possível adicionar lote a um toner inativo.")
        if payload.data_entrada.tzinfo is None:
            raise BusinessRuleError("A data de entrada deve incluir fuso horário.")
        lot = LoteToner(
            toner_id=toner.id,
            numero_lote=payload.numero_lote.strip(),
            data_entrada=payload.data_entrada,
            quantidade_inicial=payload.quantidade,
            quantidade_atual=payload.quantidade,
            validade=payload.validade,
            nota_fiscal=payload.nota_fiscal,
            fornecedor=payload.fornecedor,
            ativo=True,
        )
        self.db.add(lot)
        self.db.flush()
        self.db.add(
            MovimentacaoToner(
                lote_id=lot.id,
                toner_id=toner.id,
                tipo=TipoMovimentacao.ENTRADA,
                quantidade=payload.quantidade,
                usuario_id=usuario.id,
                criado_em=payload.data_entrada,
                observacao=f"Entrada do lote {payload.numero_lote.strip()}.",
            )
        )
        self.db.flush()
        return lot

    def consumir(
        self, toner_id: UUID, quantidade: int, usuario: Usuario, os_id: UUID | None, observacao: str | None
    ) -> list[MovimentacaoToner]:
        return consumir_fifo(self.db, toner_id, quantidade, usuario.id, os_id, observacao)

    def fila_fifo(self, toner_id: UUID) -> list[FilaFIFOItem]:
        if self.repository.obter(toner_id) is None:
            raise NotFoundError("Toner não encontrado.")
        lots = self.repository.lotes_fifo(toner_id)
        return [
            FilaFIFOItem(
                posicao=position,
                lote_id=lot.id,
                numero_lote=lot.numero_lote,
                data_entrada=lot.data_entrada,
                quantidade_atual=lot.quantidade_atual,
                validade=lot.validade,
            )
            for position, lot in enumerate(lots, start=1)
        ]

    def estoque_critico(self, limit: int, offset: int) -> tuple[list[TonerOut], int]:
        """Retorna toners ativos cujo saldo total está abaixo do mínimo cadastrado."""
        all_toners = self.db.scalars(select(Toner).where(Toner.ativo.is_(True)).order_by(Toner.modelo, Toner.id)).all()
        critical = [self._para_resposta(toner) for toner in all_toners]
        critical = [toner for toner in critical if toner.estoque_atual < toner.estoque_minimo]
        return critical[offset : offset + limit], len(critical)

    def movimentacoes(
        self, toner_id: UUID, limit: int, offset: int
    ) -> tuple[list[MovimentacaoTonerOut], int]:
        if self.repository.obter(toner_id) is None:
            raise NotFoundError("Toner não encontrado.")
        rows, total = self.repository.movimentacoes(toner_id, limit, offset)
        return [MovimentacaoTonerOut.model_validate(row) for row in rows], total