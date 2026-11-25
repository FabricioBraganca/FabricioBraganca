from datetime import time

import pytest
from pydantic import ValidationError

from toner_api.models.enums import TipoEquipamento
from toner_api.schemas.config import HorarioFuncionamentoCreate
from toner_api.schemas.equipment import EquipamentoCreate
from toner_api.schemas.toners import ConsumoToner
from toner_api.schemas.users import UsuarioCreate


def test_user_schema_rejects_malformed_email_and_short_password() -> None:
    with pytest.raises(ValidationError):
        UsuarioCreate(nome="Usuário", email="email-inválido", senha="curta", perfil="ADMIN")


def test_equipment_schema_accepts_typed_equipment_fields_for_service_validation() -> None:
    equipment = EquipamentoCreate(
        tipo=TipoEquipamento.IMPRESSORA,
        patrimonio="PAT-100",
        numero_serie="SN-100",
        marca="Fabricante",
        modelo="Modelo laser",
        localizacao="TI / sala 1",
        modelo_toner_compativel="TN-100",
    )

    assert equipment.tipo is TipoEquipamento.IMPRESSORA
    assert equipment.hostname is None


def test_schemas_reject_invalid_working_windows_and_nonpositive_stock() -> None:
    with pytest.raises(ValidationError):
        HorarioFuncionamentoCreate(
            dia_semana=0,
            hora_inicio=time(18, 0),
            hora_fim=time(8, 0),
        )
    with pytest.raises(ValidationError):
        ConsumoToner(quantidade=0)