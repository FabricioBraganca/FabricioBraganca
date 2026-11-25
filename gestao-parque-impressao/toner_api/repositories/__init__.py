"""Camada de acesso e persistência de dados."""

from toner_api.repositories.common import paginar
from toner_api.repositories.equipment import EquipamentoRepository
from toner_api.repositories.os import OrdemServicoRepository
from toner_api.repositories.toners import TonerRepository
from toner_api.repositories.users import UsuarioRepository

__all__ = [
    "EquipamentoRepository",
    "OrdemServicoRepository",
    "TonerRepository",
    "UsuarioRepository",
    "paginar",
]