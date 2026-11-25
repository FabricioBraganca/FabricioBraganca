"""Contratos de usuários e credenciais."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from toner_api.models.enums import Perfil
from toner_api.schemas.common import ORMModel


class UsuarioCreate(ORMModel):
    nome: str = Field(min_length=1, max_length=160)
    email: EmailStr
    senha: str = Field(min_length=12, max_length=72)
    perfil: Perfil
    setor: str | None = Field(default=None, max_length=120)

    @field_validator("senha")
    @classmethod
    def senha_cabe_no_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("A senha não pode exceder 72 bytes.")
        return value


class UsuarioUpdate(ORMModel):
    nome: str | None = Field(default=None, min_length=1, max_length=160)
    email: EmailStr | None = None
    nova_senha: str | None = Field(default=None, min_length=12, max_length=72)
    perfil: Perfil | None = None
    setor: str | None = Field(default=None, max_length=120)
    ativo: bool | None = None

    @field_validator("nova_senha")
    @classmethod
    def nova_senha_cabe_no_bcrypt(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("A senha não pode exceder 72 bytes.")
        return value


class UsuarioOut(ORMModel):
    id: UUID
    nome: str
    email: EmailStr
    perfil: Perfil
    setor: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class LoginRequest(ORMModel):
    email: EmailStr
    senha: str


class RefreshRequest(ORMModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(ORMModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"