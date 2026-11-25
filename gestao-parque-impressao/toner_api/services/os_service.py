"""Casos de uso de OS, autorização por recurso e cálculo de SLA."""

from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, datetime
from typing import AbstractSet
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from toner_api.core.errors import BusinessRuleError, NotFoundError
from toner_api.db.base import utc_now
from toner_api.models.enums import Perfil, Prioridade, StatusOS, StatusSLA, TipoOS
from toner_api.models.equipment import Equipamento
from toner_api.models.sla import Feriado, HorarioFuncionamento, SlaConfig
from toner_api.models.users import Usuario
from toner_api.models.work_orders import HistoricoOS, OrdemServico
from toner_api.repositories.os import OrdemServicoRepository
from toner_api.schemas.os import DashboardOS, OrdemServicoCreate, OrdemServicoOut, OrdemServicoUpdate
from toner_api.services.os_state_machine import aplicar_transicao
from toner_api.services.sla_service import HORARIOS_PADRAO, HorarioUtil, calcular_sla, horas_uteis_entre


class OrdemServicoService:
    """Coordena ciclo de vida, histórico, escopo de acesso e SLA de OS."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = OrdemServicoRepository(db)

    def _calendario(self) -> tuple[Sequence[HorarioUtil], AbstractSet[date]]:
        schedules = tuple(
            self.db.scalars(select(HorarioFuncionamento).where(HorarioFuncionamento.ativo.is_(True))).all()
        )
        holidays = frozenset(self.db.scalars(select(Feriado.data)).all())
        return (schedules or HORARIOS_PADRAO), holidays

    def _configuracoes_sla(self) -> dict[UUID, SlaConfig]:
        return {config.id: config for config in self.db.scalars(select(SlaConfig)).all()}

    def _para_resposta(
        self,
        os: OrdemServico,
        agora: datetime,
        horarios: Sequence[HorarioUtil] | None = None,
        feriados: AbstractSet[date] | None = None,
        configs: dict[UUID, SlaConfig] | None = None,
    ) -> OrdemServicoOut:
        schedule, holidays = (horarios, feriados) if horarios is not None and feriados is not None else self._calendario()
        sla_configs = configs or self._configuracoes_sla()
        config = sla_configs.get(os.sla_config_id)
        if config is None:
            raise BusinessRuleError("A configuração de SLA da OS não foi encontrada.")
        calculated = calcular_sla(os, config, agora, schedule, holidays)
        fields = {column.key: getattr(os, column.key) for column in OrdemServico.__table__.columns}
        fields.update(asdict(calculated))
        return OrdemServicoOut.model_validate(fields)

    def criar(self, payload: OrdemServicoCreate, solicitante: Usuario) -> OrdemServicoOut:
        """Abre OS com prioridade/SLA corretos e registra o evento inicial."""
        equipamento = self.db.get(Equipamento, payload.equipamento_id)
        if equipamento is None:
            raise NotFoundError("Equipamento não encontrado.")
        if equipamento.status_operacional.value in {"INATIVO", "DESCARTADO"}:
            raise BusinessRuleError("Não é possível abrir OS para equipamento inativo ou descartado.")
        if equipamento.papel_no_parque.value == "BACKUP" and payload.tipo == TipoOS.CORRETIVA:
            raise BusinessRuleError("Equipamento BACKUP deve ser promovido antes de receber OS corretiva.")
        sla_config = self.db.scalar(
            select(SlaConfig).where(SlaConfig.prioridade == payload.prioridade, SlaConfig.ativo.is_(True))
        )
        if sla_config is None:
            raise BusinessRuleError(f"Não há SLA ativo para prioridade {payload.prioridade.value}.")

        now = utc_now()
        year = now.year
        if self.db.get_bind().dialect.name == "postgresql":
            self.db.execute(text("LOCK TABLE ordens_servico IN EXCLUSIVE MODE"))
        latest = self.db.scalar(
            select(func.max(OrdemServico.numero_os)).where(OrdemServico.numero_os.like(f"OS-{year}-%"))
        )
        next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
        os = OrdemServico(
            numero_os=f"OS-{year}-{next_number:06d}",
            equipamento_id=equipamento.id,
            solicitante_id=solicitante.id,
            tecnico_id=None,
            tipo=payload.tipo,
            prioridade=payload.prioridade,
            status=StatusOS.ABERTA,
            descricao_problema=payload.descricao_problema.strip(),
            aberta_em=now,
            sla_config_id=sla_config.id,
            sla_tempo_pausado_segundos=0,
        )
        self.repository.adicionar(os)
        self.repository.adicionar_historico(
            HistoricoOS(
                os_id=os.id,
                status_anterior=None,
                status_novo=StatusOS.ABERTA,
                usuario_id=solicitante.id,
                criado_em=now,
                observacao="OS aberta.",
            )
        )
        return self._para_resposta(os, now)

    def _obter_autorizada(self, os_id: UUID, usuario: Usuario) -> OrdemServico:
        if usuario.perfil == Perfil.ADMIN:
            order = self.repository.obter(os_id)
        elif usuario.perfil == Perfil.SOLICITANTE:
            order = self.repository.obter_do_solicitante(os_id, usuario.id)
        else:
            order = self.repository.obter(os_id)
            if order is not None and order.tecnico_id != usuario.id:
                order = None
        if order is None:
            raise NotFoundError("Ordem de serviço não encontrada.")
        return order

    def obter(self, os_id: UUID, usuario: Usuario) -> OrdemServicoOut:
        order = self._obter_autorizada(os_id, usuario)
        return self._para_resposta(order, utc_now())

    def listar(
        self,
        usuario: Usuario,
        limit: int,
        offset: int,
        status: StatusOS | None = None,
        prioridade: Prioridade | None = None,
        tecnico_id: UUID | None = None,
        equipamento_id: UUID | None = None,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        sla_status: StatusSLA | None = None,
    ) -> tuple[list[OrdemServicoOut], int]:
        """Lista OS paginadas, sempre aplicando o escopo do perfil solicitante."""
        if inicio is not None and fim is not None and fim < inicio:
            raise BusinessRuleError("O fim do período deve ser posterior ao início.")
        if usuario.perfil == Perfil.SOLICITANTE:
            solicitante_id = usuario.id
            tecnico_id = None
        else:
            solicitante_id = None
            if usuario.perfil == Perfil.TECNICO:
                tecnico_id = usuario.id

        now = utc_now()
        schedules, holidays = self._calendario()
        configs = self._configuracoes_sla()
        if sla_status is None:
            orders, total = self.repository.listar(
                limit,
                offset,
                status,
                prioridade,
                tecnico_id,
                equipamento_id,
                solicitante_id,
                inicio,
                fim,
            )
            return [self._para_resposta(order, now, schedules, holidays, configs) for order in orders], total

        matching: list[OrdemServico] = []
        page_size = 200
        scan_offset = 0
        while True:
            batch, total = self.repository.listar(
                page_size,
                scan_offset,
                status,
                prioridade,
                tecnico_id,
                equipamento_id,
                solicitante_id,
                inicio,
                fim,
            )
            if not batch:
                break
            matching.extend(
                order
                for order in batch
                if self._para_resposta(order, now, schedules, holidays, configs).sla_status == sla_status
            )
            scan_offset += len(batch)
            if scan_offset >= total:
                break
        return (
            [self._para_resposta(order, now, schedules, holidays, configs) for order in matching[offset : offset + limit]],
            len(matching),
        )

    def atualizar(self, os_id: UUID, usuario: Usuario, payload: OrdemServicoUpdate) -> OrdemServicoOut:
        """Atualiza OS atribuída ou registra resposta do solicitante em espera."""
        order = self._obter_autorizada(os_id, usuario)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise BusinessRuleError("Informe ao menos um campo para atualizar.")
        if usuario.perfil == Perfil.SOLICITANTE:
            response = changes.get("resposta_solicitante")
            if order.status != StatusOS.AGUARDANDO_USUARIO or not response:
                raise BusinessRuleError("Solicitante só pode responder quando a OS aguarda usuário.")
            if set(changes) != {"resposta_solicitante"}:
                raise BusinessRuleError("O solicitante pode enviar somente resposta à OS.")
            now = utc_now()
            order.descricao_problema += f"\n\nResposta do solicitante ({now.isoformat()}): {response.strip()}"
            self.repository.adicionar_historico(
                HistoricoOS(
                    os_id=order.id,
                    status_anterior=order.status,
                    status_novo=order.status,
                    usuario_id=usuario.id,
                    criado_em=now,
                    observacao=response.strip(),
                )
            )
        else:
            if "resposta_solicitante" in changes:
                raise BusinessRuleError("Este campo é exclusivo do solicitante da OS.")
            for field, value in changes.items():
                if isinstance(value, str):
                    value = value.strip()
                setattr(order, field, value)
            self.db.flush()
        return self._para_resposta(order, utc_now())

    def transicionar(
        self,
        os_id: UUID,
        usuario: Usuario,
        status_novo: StatusOS,
        solucao_aplicada: str | None,
        observacao: str | None,
    ) -> OrdemServicoOut:
        """Executa máquina de estados e grava auditoria no mesmo escopo transacional."""
        order = self._obter_autorizada(os_id, usuario)
        now = utc_now()
        history = aplicar_transicao(
            order,
            status_novo,
            usuario.id,
            usuario.perfil,
            now,
            solucao_aplicada,
            observacao,
            *self._calendario(),
        )
        self.repository.adicionar_historico(history)
        return self._para_resposta(order, now)

    def atribuir_tecnico(self, os_id: UUID, admin: Usuario, tecnico_id: UUID) -> OrdemServicoOut:
        """Atribui ou reatribui OS a usuário ativo com perfil técnico."""
        if admin.perfil != Perfil.ADMIN:
            raise BusinessRuleError("Somente ADMIN pode atribuir ou reatribuir OS.")
        order = self.repository.obter(os_id)
        if order is None:
            raise NotFoundError("Ordem de serviço não encontrada.")
        technician = self.db.get(Usuario, tecnico_id)
        if technician is None or not technician.ativo or technician.perfil != Perfil.TECNICO:
            raise BusinessRuleError("O usuário informado não é um técnico ativo.")
        order.tecnico_id = technician.id
        self.db.flush()
        return self._para_resposta(order, utc_now())

    def historico(self, os_id: UUID, usuario: Usuario) -> list[HistoricoOS]:
        order = self._obter_autorizada(os_id, usuario)
        return self.repository.historico(order.id)

    def dashboard(self, usuario: Usuario) -> DashboardOS:
        """Calcula contadores de estado, SLAs críticos e MTTR útil médio."""
        if usuario.perfil == Perfil.SOLICITANTE:
            raise BusinessRuleError("Solicitante não pode consultar o dashboard de OS.")
        technician_id = usuario.id if usuario.perfil == Perfil.TECNICO else None
        orders, total = self.repository.listar(200, 0, tecnico_id=technician_id)
        all_orders = list(orders)
        offset = len(all_orders)
        while offset < total:
            batch, _ = self.repository.listar(200, offset, tecnico_id=technician_id)
            if not batch:
                break
            all_orders.extend(batch)
            offset += len(batch)

        counts = {status: 0 for status in StatusOS}
        schedules, holidays = self._calendario()
        configs = self._configuracoes_sla()
        now = utc_now()
        exceeded = 0
        at_risk = 0
        durations: list[float] = []
        for order in all_orders:
            counts[order.status] += 1
            sla_status = self._para_resposta(order, now, schedules, holidays, configs).sla_status
            exceeded += sla_status == StatusSLA.EXCEDIDO
            at_risk += sla_status == StatusSLA.EM_RISCO
            if order.resolvida_em is not None:
                duration = horas_uteis_entre(order.aberta_em, order.resolvida_em, schedules, holidays)
                duration -= order.sla_tempo_pausado_segundos / 3600
                durations.append(max(0.0, duration))
        return DashboardOS(
            contadores_por_status=counts,
            os_excedidas=exceeded,
            os_em_risco=at_risk,
            mttr_medio_horas=sum(durations) / len(durations) if durations else 0.0,
        )