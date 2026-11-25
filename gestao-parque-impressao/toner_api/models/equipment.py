"""Modelo unificado de impressoras e computadores do parque."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from toner_api.db.base import Base, TimestampMixin
from toner_api.models.enums import PapelNoParque, StatusOperacional, TipoEquipamento


class Equipamento(TimestampMixin, Base):
    __tablename__ = "equipamentos"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tipo: Mapped[TipoEquipamento] = mapped_column(Enum(TipoEquipamento, name="tipo_equipamento"), nullable=False)
    patrimonio: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    numero_serie: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    marca: Mapped[str] = mapped_column(String(120), nullable=False)
    modelo: Mapped[str] = mapped_column(String(160), nullable=False)
    localizacao: Mapped[str] = mapped_column(String(180), nullable=False)
    responsavel_id: Mapped[UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    status_operacional: Mapped[StatusOperacional] = mapped_column(
        Enum(StatusOperacional, name="status_operacional"), default=StatusOperacional.ATIVO, nullable=False
    )
    papel_no_parque: Mapped[PapelNoParque] = mapped_column(
        Enum(PapelNoParque, name="papel_no_parque"), default=PapelNoParque.EM_USO, nullable=False
    )
    data_aquisicao: Mapped[date | None] = mapped_column(Date)
    data_garantia_fim: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text)

    modelo_toner_compativel: Mapped[str | None] = mapped_column(String(160))
    contador_paginas: Mapped[int | None] = mapped_column(Integer)
    ip_rede: Mapped[str | None] = mapped_column(String(45))

    hostname: Mapped[str | None] = mapped_column(String(120))
    sistema_operacional: Mapped[str | None] = mapped_column(String(160))
    memoria_ram_gb: Mapped[int | None] = mapped_column(Integer)
    armazenamento_gb: Mapped[int | None] = mapped_column(Integer)