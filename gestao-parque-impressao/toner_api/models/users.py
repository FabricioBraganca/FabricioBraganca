"""Modelo de usuários, perfis e metadados de acesso."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from toner_api.db.base import Base, TimestampMixin
from toner_api.models.enums import Perfil


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuarios"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[Perfil] = mapped_column(Enum(Perfil, name="perfil_usuario"), nullable=False)
    setor: Mapped[str | None] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)