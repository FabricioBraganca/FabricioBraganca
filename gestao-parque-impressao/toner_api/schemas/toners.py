"""Contratos para catálogo, FIFO e movimentações de toner."""

from datetime import date, datetime, timezone
from uuid import UUID

from pydantic import Field

from toner_api.models.enums import CorToner, TipoMovimentacao
from toner_api.schemas.common import ORMModel


def now_utc() -> datetime:
    """Retorna o horário atual em UTC para registrar entradas de lote."""
    return datetime.now(timezone.utc)


class TonerCreate(ORMModel):
    modelo: str = Field(min_length=1, max_length=160)
    cor: CorToner
    compatibilidade: list[str] = Field(default_factory=list)
    estoque_minimo: int = Field(default=0, ge=0)
    ativo: bool = True


class TonerUpdate(ORMModel):
    modelo: str | None = Field(default=None, min_length=1, max_length=160)
    cor: CorToner | None = None
    compatibilidade: list[str] | None = None
    estoque_minimo: int | None = Field(default=None, ge=0)
    ativo: bool | None = None


class TonerOut(ORMModel):
    id: UUID
    modelo: str
    cor: CorToner
    compatibilidade: list[str]
    estoque_minimo: int
    ativo: bool
    estoque_atual: int = 0
    abaixo_minimo: bool = False


class LoteTonerCreate(ORMModel):
    numero_lote: str = Field(min_length=1, max_length=120)
    data_entrada: datetime = Field(default_factory=now_utc)
    quantidade: int = Field(gt=0)
    validade: date | None = None
    nota_fiscal: str | None = Field(default=None, max_length=120)
    fornecedor: str | None = Field(default=None, max_length=180)


class ConsumoToner(ORMModel):
    quantidade: int = Field(gt=0)
    os_id: UUID | None = None
    observacao: str | None = Field(default=None, max_length=2000)


class FilaFIFOItem(ORMModel):
    posicao: int
    lote_id: UUID
    numero_lote: str
    data_entrada: datetime
    quantidade_atual: int
    validade: date | None


class LoteTonerOut(ORMModel):
    id: UUID
    toner_id: UUID
    numero_lote: str
    data_entrada: datetime
    quantidade_inicial: int
    quantidade_atual: int
    validade: date | None
    nota_fiscal: str | None
    fornecedor: str | None
    ativo: bool


class MovimentacaoTonerOut(ORMModel):
    id: UUID
    lote_id: UUID
    toner_id: UUID
    os_id: UUID | None
    tipo: TipoMovimentacao
    quantidade: int
    usuario_id: UUID
    criado_em: datetime
    observacao: str | None


class ConsumoTonerOut(ORMModel):
    quantidade: int
    movimentacoes: list[MovimentacaoTonerOut]