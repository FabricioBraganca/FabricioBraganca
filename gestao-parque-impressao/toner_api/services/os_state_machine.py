"""Máquina de estados e pausa de SLA do ciclo de vida da OS."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import AbstractSet
from uuid import UUID

from toner_api.core.errors import BusinessRuleError
from toner_api.models.enums import Perfil, StatusOS
from toner_api.models.work_orders import HistoricoOS, OrdemServico
from toner_api.services.sla_service import HORARIOS_PADRAO, HorarioUtil, horas_uteis_entre

TRANSICOES_VALIDAS: dict[StatusOS, frozenset[StatusOS]] = {
    StatusOS.ABERTA: frozenset({StatusOS.EM_ANDAMENTO, StatusOS.CANCELADA}),
    StatusOS.EM_ANDAMENTO: frozenset(
        {StatusOS.AGUARDANDO_USUARIO, StatusOS.AGUARDANDO_PECA, StatusOS.RESOLVIDA, StatusOS.CANCELADA}
    ),
    StatusOS.AGUARDANDO_USUARIO: frozenset({StatusOS.EM_ANDAMENTO, StatusOS.CANCELADA}),
    StatusOS.AGUARDANDO_PECA: frozenset({StatusOS.EM_ANDAMENTO, StatusOS.CANCELADA}),
    StatusOS.RESOLVIDA: frozenset({StatusOS.EM_ANDAMENTO}),
    StatusOS.CANCELADA: frozenset(),
}


def validar_transicao(
    status_atual: StatusOS,
    status_novo: StatusOS,
    perfil: Perfil,
    solucao_aplicada: str | None = None,
) -> None:
    """Valida permissões, aresta de estado e dados obrigatórios da resolução."""
    if perfil not in {Perfil.ADMIN, Perfil.TECNICO}:
        raise BusinessRuleError("Somente ADMIN ou o técnico atribuído pode alterar o status da OS.")
    if status_novo not in TRANSICOES_VALIDAS[status_atual]:
        raise BusinessRuleError(f"Transição de {status_atual.value} para {status_novo.value} não permitida.")
    if status_atual == StatusOS.RESOLVIDA and perfil != Perfil.ADMIN:
        raise BusinessRuleError("Somente ADMIN pode reabrir uma OS resolvida.")
    if status_novo == StatusOS.RESOLVIDA and not (solucao_aplicada or "").strip():
        raise BusinessRuleError("Informe a solução aplicada antes de resolver a OS.")


def aplicar_transicao(
    os: OrdemServico,
    status_novo: StatusOS,
    usuario_id: UUID,
    perfil: Perfil,
    agora: datetime,
    solucao_aplicada: str | None = None,
    observacao: str | None = None,
    horarios: Sequence[HorarioUtil] = HORARIOS_PADRAO,
    feriados: AbstractSet[date] = frozenset(),
) -> HistoricoOS:
    """Aplica uma transição autorizada, atualiza timestamps e retorna sua auditoria."""
    status_anterior = os.status
    validar_transicao(status_anterior, status_novo, perfil, solucao_aplicada or os.solucao_aplicada)
    if perfil == Perfil.TECNICO and os.tecnico_id != usuario_id:
        raise BusinessRuleError("Técnicos só podem alterar OS atribuídas a eles.")

    if status_anterior == StatusOS.AGUARDANDO_USUARIO and status_novo != StatusOS.AGUARDANDO_USUARIO:
        if os.sla_pausado_em is not None:
            horas_pausadas = horas_uteis_entre(os.sla_pausado_em, agora, horarios, feriados)
            os.sla_tempo_pausado_segundos += round(horas_pausadas * 3600)
            os.sla_pausado_em = None
    elif status_novo == StatusOS.AGUARDANDO_USUARIO:
        os.sla_pausado_em = agora

    if status_novo == StatusOS.EM_ANDAMENTO:
        if os.primeira_resposta_em is None:
            os.primeira_resposta_em = agora
        if os.iniciada_em is None:
            os.iniciada_em = agora
        os.resolvida_em = None
    elif status_novo == StatusOS.RESOLVIDA:
        os.solucao_aplicada = (solucao_aplicada or os.solucao_aplicada or "").strip()
        os.resolvida_em = agora
    elif status_novo == StatusOS.CANCELADA:
        os.cancelada_em = agora

    os.status = status_novo
    return HistoricoOS(
        os_id=os.id,
        status_anterior=status_anterior,
        status_novo=status_novo,
        usuario_id=usuario_id,
        criado_em=agora,
        observacao=observacao,
    )