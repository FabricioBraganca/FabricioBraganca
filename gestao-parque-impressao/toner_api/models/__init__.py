"""Modelos ORM da aplicação e exportação para registro do metadata."""

from toner_api.models.equipment import Equipamento
from toner_api.models.sla import Feriado, HorarioFuncionamento, SlaConfig
from toner_api.models.toners import LoteToner, MovimentacaoToner, Toner
from toner_api.models.users import Usuario
from toner_api.models.work_orders import HistoricoOS, OrdemServico

__all__ = [
    "Equipamento",
    "Feriado",
    "HistoricoOS",
    "HorarioFuncionamento",
    "LoteToner",
    "MovimentacaoToner",
    "OrdemServico",
    "SlaConfig",
    "Toner",
    "Usuario",
]