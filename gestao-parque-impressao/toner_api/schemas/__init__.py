"""Schemas Pydantic v2 de entrada e saída da API."""

from toner_api.schemas.common import Pagina
from toner_api.schemas.equipment import EquipamentoCreate, EquipamentoOut, EquipamentoUpdate
from toner_api.schemas.os import OrdemServicoCreate, OrdemServicoOut, OrdemServicoUpdate
from toner_api.schemas.toners import TonerCreate, TonerOut
from toner_api.schemas.users import UsuarioCreate, UsuarioOut, UsuarioUpdate

__all__ = [
    "EquipamentoCreate",
    "EquipamentoOut",
    "EquipamentoUpdate",
    "OrdemServicoCreate",
    "OrdemServicoOut",
    "OrdemServicoUpdate",
    "Pagina",
    "TonerCreate",
    "TonerOut",
    "UsuarioCreate",
    "UsuarioOut",
    "UsuarioUpdate",
]