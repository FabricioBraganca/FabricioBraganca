"""Configuração de SLA, expediente e calendário de feriados."""

from datetime import date, time
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, Enum, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from toner_api.db.base import Base
from toner_api.models.enums import Prioridade


class SlaConfig(Base):
    __tablename__ = "sla_config"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    prioridade: Mapped[Prioridade] = mapped_column(Enum(Prioridade, name="prioridade_os"), unique=True, nullable=False)
    horas_limite_resposta: Mapped[int] = mapped_column(Integer, nullable=False)
    horas_limite_resolucao: Mapped[int] = mapped_column(Integer, nullable=False)
    considera_horas_uteis: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("horas_limite_resposta > 0", name="horas_resposta_positivas"),
        CheckConstraint("horas_limite_resolucao > 0", name="horas_resolucao_positivas"),
    )


class HorarioFuncionamento(Base):
    __tablename__ = "horarios_funcionamento"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fim: Mapped[time] = mapped_column(Time, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (CheckConstraint("dia_semana >= 0 AND dia_semana <= 6", name="dia_semana_valido"),)


class Feriado(Base):
    __tablename__ = "feriados"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    data: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)