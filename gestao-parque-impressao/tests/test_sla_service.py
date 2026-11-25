from datetime import date, datetime, time

from toner_api.models.enums import Prioridade, StatusOS, StatusSLA
from toner_api.models.sla import SlaConfig
from toner_api.models.work_orders import OrdemServico
from toner_api.services.sla_service import JanelaTrabalho, calcular_sla, horas_uteis_entre, somar_horas_uteis


def test_business_hours_skip_weekend_and_holiday() -> None:
    holiday = date(2026, 11, 23)
    start = datetime(2026, 11, 20, 17, 0)

    result = somar_horas_uteis(start, 2, feriados={holiday})

    assert result == datetime(2026, 11, 24, 9, 0)
    assert horas_uteis_entre(start, result, feriados={holiday}) == 2


def test_opening_outside_working_hours_starts_at_next_window() -> None:
    start = datetime(2026, 11, 20, 20, 0)

    assert somar_horas_uteis(start, 1) == datetime(2026, 11, 23, 9, 0)


def test_multiple_windows_exclude_lunch_break() -> None:
    windows = (JanelaTrabalho(0, time(8), time(12)), JanelaTrabalho(0, time(13), time(17)))

    assert horas_uteis_entre(datetime(2026, 11, 23, 11), datetime(2026, 11, 23, 14), windows) == 2


def test_sla_reports_risk_and_exceeded_response_deadlines() -> None:
    config = SlaConfig(
        prioridade=Prioridade.MEDIA,
        horas_limite_resposta=8,
        horas_limite_resolucao=48,
        considera_horas_uteis=True,
        ativo=True,
    )
    order = OrdemServico(
        aberta_em=datetime(2026, 11, 23, 8),
        primeira_resposta_em=None,
        sla_tempo_pausado_segundos=0,
        sla_pausado_em=None,
        status=StatusOS.ABERTA,
    )

    at_risk = calcular_sla(order, config, datetime(2026, 11, 23, 15))
    overdue = calcular_sla(order, config, datetime(2026, 11, 23, 17))

    assert at_risk.sla_status == StatusSLA.EM_RISCO
    assert at_risk.tempo_restante_horas == 1
    assert overdue.sla_status == StatusSLA.EXCEDIDO
    assert overdue.excedido_por_horas == 1