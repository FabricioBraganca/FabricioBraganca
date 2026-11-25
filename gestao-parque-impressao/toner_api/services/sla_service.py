"""Cálculos isolados de expediente útil, prazos e métricas de SLA."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import AbstractSet

from toner_api.models.enums import StatusOS, StatusSLA
from toner_api.models.sla import HorarioFuncionamento, SlaConfig
from toner_api.models.work_orders import OrdemServico


@dataclass(frozen=True)
class JanelaTrabalho:
    """Intervalo ativo de expediente para um dia da semana."""

    dia_semana: int
    hora_inicio: time
    hora_fim: time


HorarioUtil = JanelaTrabalho | HorarioFuncionamento
HORARIOS_PADRAO = tuple(JanelaTrabalho(day, time(8), time(18)) for day in range(5))


@dataclass(frozen=True)
class ResultadoSLA:
    """Valores calculados para apresentação; não devem ser persistidos."""

    prazo_resposta: datetime
    prazo_resolucao: datetime
    tempo_decorrido_horas: float
    tempo_restante_horas: float
    sla_status: StatusSLA
    excedido_por_horas: float


def _windows_for_day(dia: date, horarios: Sequence[HorarioUtil]) -> list[tuple[time, time]]:
    """Normaliza janelas de domínio e ORM, excluindo intervalos inativos."""
    return sorted(
        (
            (window.hora_inicio, window.hora_fim)
            for window in horarios
            if window.dia_semana == dia.weekday()
            and (not isinstance(window, HorarioFuncionamento) or window.ativo)
        ),
        key=lambda interval: interval[0],
    )


def _combine(dia: date, horario: time, reference: datetime) -> datetime:
    """Combina data e hora preservando o fuso do instante de referência."""
    return datetime.combine(dia, horario, tzinfo=reference.tzinfo)


def _align_timezone(value: datetime, reference: datetime) -> datetime:
    """Alinha timestamps ingênuos ao fuso de referência, como no SQLite."""
    if reference.tzinfo is None and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if reference.tzinfo is not None and value.tzinfo is None:
        return value.replace(tzinfo=reference.tzinfo)
    return value


def somar_horas_uteis(
    inicio: datetime,
    horas: float,
    horarios: Sequence[HorarioUtil] = HORARIOS_PADRAO,
    feriados: AbstractSet[date] = frozenset(),
) -> datetime:
    """Soma horas apenas em janelas ativas, pulando noites, fins de semana e feriados."""
    if horas < 0:
        raise ValueError("A quantidade de horas úteis não pode ser negativa.")
    if horas == 0:
        return inicio

    restante = horas * 3600
    cursor = inicio
    while restante > 1e-7:
        if cursor.date() not in feriados:
            for hora_inicio, hora_fim in _windows_for_day(cursor.date(), horarios):
                janela_inicio = _combine(cursor.date(), hora_inicio, cursor)
                janela_fim = _combine(cursor.date(), hora_fim, cursor)
                if cursor >= janela_fim:
                    continue
                cursor = max(cursor, janela_inicio)
                disponivel = (janela_fim - cursor).total_seconds()
                if restante <= disponivel:
                    return cursor + timedelta(seconds=restante)
                restante -= disponivel
                cursor = janela_fim
        proximo_dia = cursor.date() + timedelta(days=1)
        cursor = _combine(proximo_dia, time.min, cursor)
    return cursor


def horas_uteis_entre(
    inicio: datetime,
    fim: datetime,
    horarios: Sequence[HorarioUtil] = HORARIOS_PADRAO,
    feriados: AbstractSet[date] = frozenset(),
) -> float:
    """Calcula horas de expediente entre dois instantes, excluindo feriados."""
    fim = _align_timezone(fim, inicio)
    if fim < inicio:
        raise ValueError("O instante final não pode anteceder o instante inicial.")
    if fim == inicio:
        return 0.0

    total_segundos = 0.0
    dia = inicio.date()
    while dia <= fim.date():
        if dia not in feriados:
            for hora_inicio, hora_fim in _windows_for_day(dia, horarios):
                janela_inicio = _combine(dia, hora_inicio, inicio)
                janela_fim = _combine(dia, hora_fim, inicio)
                sobreposicao_inicio = max(inicio, janela_inicio)
                sobreposicao_fim = min(fim, janela_fim)
                if sobreposicao_fim > sobreposicao_inicio:
                    total_segundos += (sobreposicao_fim - sobreposicao_inicio).total_seconds()
        dia += timedelta(days=1)
    return total_segundos / 3600


def calcular_sla(
    os: OrdemServico,
    config: SlaConfig,
    agora: datetime,
    horarios: Sequence[HorarioUtil] = HORARIOS_PADRAO,
    feriados: AbstractSet[date] = frozenset(),
) -> ResultadoSLA:
    """Calcula prazos e status da OS sem gravar valores derivados no banco."""
    agora = _align_timezone(agora, os.aberta_em)
    sla_pausado_em = (
        _align_timezone(os.sla_pausado_em, os.aberta_em) if os.sla_pausado_em is not None else None
    )
    if not config.considera_horas_uteis:
        horarios = tuple(JanelaTrabalho(day, time.min, time.max) for day in range(7))
        feriados = frozenset()
    pausa_acumulada_horas = os.sla_tempo_pausado_segundos / 3600
    pausado = sla_pausado_em is not None or os.status == StatusOS.AGUARDANDO_USUARIO
    if sla_pausado_em is not None:
        pausa_acumulada_horas += horas_uteis_entre(sla_pausado_em, agora, horarios, feriados)

    prazo_resposta = somar_horas_uteis(
        os.aberta_em, config.horas_limite_resposta + pausa_acumulada_horas, horarios, feriados
    )
    prazo_resolucao = somar_horas_uteis(
        os.aberta_em, config.horas_limite_resolucao + pausa_acumulada_horas, horarios, feriados
    )
    tempo_decorrido = horas_uteis_entre(os.aberta_em, agora, horarios, feriados)
    tempo_decorrido = max(0.0, tempo_decorrido - pausa_acumulada_horas)

    prazo_atual = prazo_resposta if os.primeira_resposta_em is None else prazo_resolucao
    limite_atual = config.horas_limite_resposta if os.primeira_resposta_em is None else config.horas_limite_resolucao
    if agora <= prazo_atual:
        tempo_restante = horas_uteis_entre(agora, prazo_atual, horarios, feriados)
    else:
        tempo_restante = -horas_uteis_entre(prazo_atual, agora, horarios, feriados)

    if pausado:
        sla_status = StatusSLA.PAUSADO
    elif tempo_restante <= 0:
        sla_status = StatusSLA.EXCEDIDO
    elif tempo_restante < limite_atual * 0.2:
        sla_status = StatusSLA.EM_RISCO
    else:
        sla_status = StatusSLA.DENTRO_DO_PRAZO

    return ResultadoSLA(
        prazo_resposta=prazo_resposta,
        prazo_resolucao=prazo_resolucao,
        tempo_decorrido_horas=tempo_decorrido,
        tempo_restante_horas=tempo_restante,
        sla_status=sla_status,
        excedido_por_horas=max(0.0, -tempo_restante),
    )