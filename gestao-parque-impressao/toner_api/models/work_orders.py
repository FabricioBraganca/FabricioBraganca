"""Ordens de serviço e trilha de auditoria de transições."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from toner_api.db.base import Base, TimestampMixin, utc_now
from toner_api.models.enums import Prioridade, StatusOS, TipoOS


class OrdemServico(TimestampMixin, Base):
    __tablename__ = "ordens_servico"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    numero_os: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    equipamento_id: Mapped[UUID] = mapped_column(ForeignKey("equipamentos.id", ondelete="RESTRICT"), index=True)
    solicitante_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    tecnico_id: Mapped[UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    tipo: Mapped[TipoOS] = mapped_column(Enum(TipoOS, name="tipo_os"), nullable=False)
    prioridade: Mapped[Prioridade] = mapped_column(Enum(Prioridade, name="prioridade_os"), nullable=False)
    status: Mapped[StatusOS] = mapped_column(
        Enum(StatusOS, name="status_os"), default=StatusOS.ABERTA, nullable=False, index=True
    )
    descricao_problema: Mapped[str] = mapped_column(Text, nullable=False)
    solucao_aplicada: Mapped[str | None] = mapped_column(Text)
    aberta_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    primeira_resposta_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_config_id: Mapped[UUID] = mapped_column(ForeignKey("sla_config.id", ondelete="RESTRICT"), nullable=False)
    sla_pausado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_tempo_pausado_segundos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class HistoricoOS(Base):
    __tablename__ = "historico_os"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    os_id: Mapped[UUID] = mapped_column(ForeignKey("ordens_servico.id", ondelete="CASCADE"), index=True)
    status_anterior: Mapped[StatusOS | None] = mapped_column(Enum(StatusOS, name="status_os"))
    status_novo: Mapped[StatusOS] = mapped_column(Enum(StatusOS, name="status_os"), nullable=False)
    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)