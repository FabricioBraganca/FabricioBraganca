"""Consumo transacional de lotes de toner na ordem FIFO."""

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from toner_api.core.errors import ConflictError, NotFoundError
from toner_api.db.base import utc_now
from toner_api.models.enums import TipoMovimentacao
from toner_api.models.toners import LoteToner, MovimentacaoToner, Toner
from toner_api.models.users import Usuario
from toner_api.models.work_orders import OrdemServico


def listar_lotes_fifo(db: Session, toner_id: UUID) -> Sequence[LoteToner]:
    """Lista lotes com saldo em ordem de entrada para exibir a fila FIFO."""
    if db.get(Toner, toner_id) is None:
        raise NotFoundError("Toner não encontrado.")
    return db.scalars(
        select(LoteToner)
        .where(LoteToner.toner_id == toner_id, LoteToner.ativo.is_(True), LoteToner.quantidade_atual > 0)
        .order_by(LoteToner.data_entrada, LoteToner.id)
    ).all()


def consumir_fifo(
    db: Session,
    toner_id: UUID,
    quantidade: int,
    usuario_id: UUID,
    os_id: UUID | None = None,
    observacao: str | None = None,
    agora: datetime | None = None,
    hoje: date | None = None,
) -> list[MovimentacaoToner]:
    """Baixa estoque válido do lote mais antigo para o mais novo, em uma transação."""
    if quantidade <= 0:
        raise ValueError("A quantidade para consumo deve ser positiva.")
    toner = db.get(Toner, toner_id)
    if toner is None:
        raise NotFoundError("Toner não encontrado.")
    if not toner.ativo:
        raise ConflictError("Não é possível consumir um toner inativo.")
    if db.get(Usuario, usuario_id) is None:
        raise NotFoundError("Usuário não encontrado.")
    if os_id is not None and db.get(OrdemServico, os_id) is None:
        raise NotFoundError("Ordem de serviço não encontrada.")

    dia_atual = hoje or date.today()
    lotes = db.scalars(
        select(LoteToner)
        .where(LoteToner.toner_id == toner_id, LoteToner.ativo.is_(True), LoteToner.quantidade_atual > 0)
        .order_by(LoteToner.data_entrada, LoteToner.id)
        .with_for_update()
    ).all()
    lotes_validos = [lote for lote in lotes if lote.validade is None or lote.validade >= dia_atual]
    disponivel = sum(lote.quantidade_atual for lote in lotes_validos)
    if disponivel < quantidade:
        vencido = sum(lote.quantidade_atual for lote in lotes if lote.validade is not None and lote.validade < dia_atual)
        detalhe_vencido = f" Há {vencido} unidade(s) em lote(s) vencido(s)." if vencido else ""
        raise ConflictError(f"Estoque insuficiente: {disponivel} unidade(s) válida(s) disponível(is).{detalhe_vencido}")

    restante = quantidade
    movimentacoes: list[MovimentacaoToner] = []
    criado_em = agora or utc_now()
    for lote in lotes_validos:
        usada = min(lote.quantidade_atual, restante)
        if usada == 0:
            continue
        lote.quantidade_atual -= usada
        movement = MovimentacaoToner(
            lote_id=lote.id,
            toner_id=toner_id,
            os_id=os_id,
            tipo=TipoMovimentacao.SAIDA,
            quantidade=usada,
            usuario_id=usuario_id,
            criado_em=criado_em,
            observacao=observacao,
        )
        db.add(movement)
        movimentacoes.append(movement)
        restante -= usada
        if restante == 0:
            break
    db.flush()
    return movimentacoes