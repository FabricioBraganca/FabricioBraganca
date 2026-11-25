"""Contratos de cadastro, consulta e atualização de equipamentos."""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from toner_api.models.enums import PapelNoParque, StatusOperacional, TipoEquipamento
from toner_api.schemas.common import ORMModel


class EquipamentoCreate(ORMModel):
    tipo: TipoEquipamento
    patrimonio: str = Field(min_length=1, max_length=80)
    numero_serie: str = Field(min_length=1, max_length=120)
    marca: str = Field(min_length=1, max_length=120)
    modelo: str = Field(min_length=1, max_length=160)
    localizacao: str = Field(min_length=1, max_length=180)
    responsavel_id: UUID | None = None
    status_operacional: StatusOperacional = StatusOperacional.ATIVO
    papel_no_parque: PapelNoParque = PapelNoParque.EM_USO
    data_aquisicao: date | None = None
    data_garantia_fim: date | None = None
    observacoes: str | None = None
    modelo_toner_compativel: str | None = Field(default=None, max_length=160)
    contador_paginas: int | None = Field(default=None, ge=0)
    ip_rede: str | None = Field(default=None, max_length=45)
    hostname: str | None = Field(default=None, max_length=120)
    sistema_operacional: str | None = Field(default=None, max_length=160)
    memoria_ram_gb: int | None = Field(default=None, gt=0)
    armazenamento_gb: int | None = Field(default=None, gt=0)


class EquipamentoUpdate(ORMModel):
    tipo: TipoEquipamento | None = None
    patrimonio: str | None = Field(default=None, min_length=1, max_length=80)
    numero_serie: str | None = Field(default=None, min_length=1, max_length=120)
    marca: str | None = Field(default=None, min_length=1, max_length=120)
    modelo: str | None = Field(default=None, min_length=1, max_length=160)
    localizacao: str | None = Field(default=None, min_length=1, max_length=180)
    responsavel_id: UUID | None = None
    status_operacional: StatusOperacional | None = None
    papel_no_parque: PapelNoParque | None = None
    data_aquisicao: date | None = None
    data_garantia_fim: date | None = None
    observacoes: str | None = None
    modelo_toner_compativel: str | None = Field(default=None, max_length=160)
    contador_paginas: int | None = Field(default=None, ge=0)
    ip_rede: str | None = Field(default=None, max_length=45)
    hostname: str | None = Field(default=None, max_length=120)
    sistema_operacional: str | None = Field(default=None, max_length=160)
    memoria_ram_gb: int | None = Field(default=None, gt=0)
    armazenamento_gb: int | None = Field(default=None, gt=0)


class EquipamentoOut(EquipamentoCreate):
    id: UUID
    criado_em: datetime
    atualizado_em: datetime


class EquipamentoParqueResumo(ORMModel):
    total_em_uso: int
    total_backup: int
    taxa_ocupacao: float
    backups_disponiveis_por_tipo: dict[TipoEquipamento, int]