from datetime import datetime
from uuid import uuid4

import pytest

from toner_api.core.errors import BusinessRuleError
from toner_api.models.enums import Perfil, StatusOS
from toner_api.models.work_orders import OrdemServico
from toner_api.services.os_state_machine import aplicar_transicao, validar_transicao


def test_valid_and_invalid_status_transitions() -> None:
    validar_transicao(StatusOS.ABERTA, StatusOS.EM_ANDAMENTO, Perfil.TECNICO)
    with pytest.raises(BusinessRuleError, match="não permitida"):
        validar_transicao(StatusOS.ABERTA, StatusOS.RESOLVIDA, Perfil.ADMIN, "Solução")
    with pytest.raises(BusinessRuleError, match="solução aplicada"):
        validar_transicao(StatusOS.EM_ANDAMENTO, StatusOS.RESOLVIDA, Perfil.ADMIN)


def test_waiting_for_user_pauses_and_resume_accumulates_business_seconds() -> None:
    technician_id = uuid4()
    order = OrdemServico(
        id=uuid4(),
        tecnico_id=technician_id,
        status=StatusOS.EM_ANDAMENTO,
        sla_tempo_pausado_segundos=0,
        sla_pausado_em=None,
        primeira_resposta_em=datetime(2026, 11, 23, 9),
    )
    entered_wait = datetime(2026, 11, 23, 10)
    resumed = datetime(2026, 11, 24, 10)

    first_history = aplicar_transicao(
        order, StatusOS.AGUARDANDO_USUARIO, technician_id, Perfil.TECNICO, entered_wait
    )
    second_history = aplicar_transicao(order, StatusOS.EM_ANDAMENTO, technician_id, Perfil.TECNICO, resumed)

    assert first_history.status_anterior == StatusOS.EM_ANDAMENTO
    assert second_history.status_novo == StatusOS.EM_ANDAMENTO
    assert order.sla_pausado_em is None
    assert order.sla_tempo_pausado_segundos == 10 * 3600


def test_only_admin_can_reopen_resolved_order_and_technician_must_be_assigned() -> None:
    technician_id = uuid4()
    resolved_order = OrdemServico(id=uuid4(), tecnico_id=uuid4(), status=StatusOS.RESOLVIDA)
    assigned_to_other = OrdemServico(id=uuid4(), tecnico_id=uuid4(), status=StatusOS.EM_ANDAMENTO)

    with pytest.raises(BusinessRuleError, match="Somente ADMIN"):
        aplicar_transicao(resolved_order, StatusOS.EM_ANDAMENTO, technician_id, Perfil.TECNICO, datetime.now())
    with pytest.raises(BusinessRuleError, match="atribuídas"):
        aplicar_transicao(assigned_to_other, StatusOS.AGUARDANDO_PECA, technician_id, Perfil.TECNICO, datetime.now())