"""Catálogo de toners, lotes FIFO e movimentações imutáveis."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from toner_api.db.base import Base, utc_now
from toner_api.models.enums import CorToner, TipoMovimentacao

COMPATIBILIDADE_JSON = JSON().with_variant(JSONB, "postgresql")


class Toner(Base):
    __tablename__ = "toners"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    modelo: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cor: Mapped[CorToner] = mapped_column(Enum(CorToner, name="cor_toner"), nullable=False)
    compatibilidade: Mapped[list[str]] = mapped_column(COMPATIBILIDADE_JSON, default=list, nullable=False)
    estoque_minimo: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (CheckConstraint("estoque_minimo >= 0", name="estoque_minimo_nao_negativo"),)


class LoteToner(Base):
    __tablename__ = "lotes_toner"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    toner_id: Mapped[UUID] = mapped_column(ForeignKey("toners.id", ondelete="RESTRICT"), nullable=False)
    numero_lote: Mapped[str] = mapped_column(String(120), nullable=False)
    data_entrada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    quantidade_inicial: Mapped[int] = mapped_column(Integer, nullable=False)
    quantidade_atual: Mapped[int] = mapped_column(Integer, nullable=False)
    validade: Mapped[date | None] = mapped_column(Date)
    nota_fiscal: Mapped[str | None] = mapped_column(String(120))
    fornecedor: Mapped[str | None] = mapped_column(String(180))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("quantidade_inicial > 0", name="quantidade_inicial_positiva"),
        CheckConstraint(
            "quantidade_atual >= 0 AND quantidade_atual <= quantidade_inicial", name="quantidade_atual_valida"
        ),
        Index("ix_lotes_toner_fifo", "toner_id", "data_entrada", "id"),
    )


class MovimentacaoToner(Base):
    __tablename__ = "movimentacoes_toner"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lote_id: Mapped[UUID] = mapped_column(ForeignKey("lotes_toner.id", ondelete="RESTRICT"), nullable=False)
    toner_id: Mapped[UUID] = mapped_column(ForeignKey("toners.id", ondelete="RESTRICT"), nullable=False, index=True)
    os_id: Mapped[UUID | None] = mapped_column(ForeignKey("ordens_servico.id", ondelete="SET NULL"), index=True)
    tipo: Mapped[TipoMovimentacao] = mapped_column(Enum(TipoMovimentacao, name="tipo_movimentacao_toner"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("quantidade > 0", name="quantidade_movimentacao_positiva"),)