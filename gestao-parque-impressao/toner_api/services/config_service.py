"""Casos de uso de configuração de SLA, expediente e feriados."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toner_api.core.errors import BusinessRuleError, ConflictError
from toner_api.models.sla import Feriado, HorarioFuncionamento, SlaConfig
from toner_api.schemas.config import (
    FeriadoCreate,
    FeriadoOut,
    HorarioFuncionamentoCreate,
    HorarioFuncionamentoOut,
    SlaConfigOut,
    SlaConfigUpdate,
)


class ConfiguracaoService:
    """Consulta e altera regras de SLA e calendário de expediente."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_sla(self) -> list[SlaConfigOut]:
        configs = self.db.scalars(select(SlaConfig).order_by(SlaConfig.prioridade)).all()
        return [SlaConfigOut.model_validate(config) for config in configs]

    def atualizar_sla(self, payloads: list[SlaConfigUpdate]) -> list[SlaConfigOut]:
        """Atualiza ou cria uma configuração por prioridade sem duplicatas."""
        priorities = [payload.prioridade for payload in payloads]
        if len(priorities) != len(set(priorities)):
            raise BusinessRuleError("A requisição não pode repetir prioridades de SLA.")
        for payload in payloads:
            config = self.db.scalar(select(SlaConfig).where(SlaConfig.prioridade == payload.prioridade))
            if config is None:
                config = SlaConfig(prioridade=payload.prioridade)
                self.db.add(config)
            for field, value in payload.model_dump().items():
                setattr(config, field, value)
        self.db.flush()
        return self.listar_sla()

    def listar_horarios(self, limit: int, offset: int) -> tuple[list[HorarioFuncionamentoOut], int]:
        statement = select(HorarioFuncionamento).order_by(
            HorarioFuncionamento.dia_semana,
            HorarioFuncionamento.hora_inicio,
            HorarioFuncionamento.id,
        )
        total = self.db.scalar(select(func.count()).select_from(HorarioFuncionamento)) or 0
        rows = self.db.scalars(statement.limit(limit).offset(offset)).all()
        return [HorarioFuncionamentoOut.model_validate(row) for row in rows], total

    def criar_horario(self, payload: HorarioFuncionamentoCreate) -> HorarioFuncionamentoOut:
        """Cria intervalo sem sobreposição com janela ativa do mesmo dia."""
        if payload.ativo:
            existing = self.db.scalars(
                select(HorarioFuncionamento).where(
                    HorarioFuncionamento.dia_semana == payload.dia_semana,
                    HorarioFuncionamento.ativo.is_(True),
                )
            ).all()
            overlaps = any(
                payload.hora_inicio < item.hora_fim and item.hora_inicio < payload.hora_fim for item in existing
            )
            if overlaps:
                raise ConflictError("O intervalo sobrepõe outro horário ativo do mesmo dia.")
        record = HorarioFuncionamento(**payload.model_dump())
        self.db.add(record)
        self.db.flush()
        return HorarioFuncionamentoOut.model_validate(record)

    def listar_feriados(self, limit: int, offset: int) -> tuple[list[FeriadoOut], int]:
        statement = select(Feriado).order_by(Feriado.data, Feriado.id)
        total = self.db.scalar(select(func.count()).select_from(Feriado)) or 0
        rows = self.db.scalars(statement.limit(limit).offset(offset)).all()
        return [FeriadoOut.model_validate(row) for row in rows], total

    def criar_feriado(self, payload: FeriadoCreate) -> FeriadoOut:
        """Registra uma data excluída dos cálculos de horas úteis."""
        exists = self.db.scalar(select(Feriado.id).where(Feriado.data == payload.data))
        if exists is not None:
            raise ConflictError("Já existe feriado cadastrado para esta data.")
        record = Feriado(**payload.model_dump())
        self.db.add(record)
        self.db.flush()
        return FeriadoOut.model_validate(record)