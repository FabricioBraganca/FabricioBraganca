"""Contratos para regras de SLA, expediente e feriados."""

from datetime import date, time
from uuid import UUID

from pydantic import Field, model_validator

from toner_api.models.enums import Prioridade
from toner_api.schemas.common import ORMModel


class SlaConfigUpdate(ORMModel):
    prioridade: Prioridade
    horas_limite_resposta: int = Field(gt=0)
    horas_limite_resolucao: int = Field(gt=0)
    considera_horas_uteis: bool = True
    ativo: bool = True


class SlaConfigOut(SlaConfigUpdate):
    id: UUID


class HorarioFuncionamentoCreate(ORMModel):
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fim: time
    ativo: bool = True

    @model_validator(mode="after")
    def intervalo_crescente(self) -> "HorarioFuncionamentoCreate":
        if self.hora_fim <= self.hora_inicio:
            raise ValueError("A hora final deve ser posterior à hora inicial.")
        return self


class HorarioFuncionamentoOut(HorarioFuncionamentoCreate):
    id: UUID


class FeriadoCreate(ORMModel):
    data: date
    descricao: str = Field(min_length=1, max_length=200)


class FeriadoOut(FeriadoCreate):
    id: UUID