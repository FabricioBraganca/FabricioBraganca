"""Contratos de ordens de serviço, SLA e histórico."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from toner_api.models.enums import Prioridade, StatusOS, StatusSLA, TipoOS
from toner_api.schemas.common import ORMModel


class OrdemServicoCreate(ORMModel):
    equipamento_id: UUID
    tipo: TipoOS
    prioridade: Prioridade = Prioridade.MEDIA
    descricao_problema: str = Field(min_length=1, max_length=10000)


class OrdemServicoUpdate(ORMModel):
    prioridade: Prioridade | None = None
    descricao_problema: str | None = Field(default=None, min_length=1, max_length=10000)
    solucao_aplicada: str | None = Field(default=None, max_length=10000)
    resposta_solicitante: str | None = Field(default=None, min_length=1, max_length=4000)


class TransicaoStatusOS(ORMModel):
    status: StatusOS
    solucao_aplicada: str | None = Field(default=None, max_length=10000)
    observacao: str | None = Field(default=None, max_length=2000)


class AtribuicaoTecnico(ORMModel):
    tecnico_id: UUID


class OrdemServicoOut(ORMModel):
    id: UUID
    numero_os: str
    equipamento_id: UUID
    solicitante_id: UUID
    tecnico_id: UUID | None
    tipo: TipoOS
    prioridade: Prioridade
    status: StatusOS
    descricao_problema: str
    solucao_aplicada: str | None
    aberta_em: datetime
    primeira_resposta_em: datetime | None
    iniciada_em: datetime | None
    resolvida_em: datetime | None
    cancelada_em: datetime | None
    sla_config_id: UUID
    sla_pausado_em: datetime | None
    sla_tempo_pausado_segundos: int
    criado_em: datetime
    atualizado_em: datetime
    prazo_resposta: datetime
    prazo_resolucao: datetime
    tempo_decorrido_horas: float
    tempo_restante_horas: float
    sla_status: StatusSLA
    excedido_por_horas: float


class HistoricoOSOut(ORMModel):
    id: UUID
    os_id: UUID
    status_anterior: StatusOS | None
    status_novo: StatusOS
    usuario_id: UUID
    criado_em: datetime
    observacao: str | None


class DashboardOS(ORMModel):
    contadores_por_status: dict[StatusOS, int]
    os_excedidas: int
    os_em_risco: int
    mttr_medio_horas: float


class JanelaPeriodo(ORMModel):
    inicio: datetime | None = None
    fim: datetime | None = None

    @model_validator(mode="after")
    def periodo_crescente(self) -> "JanelaPeriodo":
        if self.inicio is not None and self.fim is not None and self.fim < self.inicio:
            raise ValueError("O fim do período deve ser posterior ao início.")
        return self