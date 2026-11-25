"""Routers REST organizados por domínio."""

from toner_api.api.routers.auth import router as auth_router
from toner_api.api.routers.config import router as config_router
from toner_api.api.routers.equipment import router as equipment_router
from toner_api.api.routers.os import router as os_router
from toner_api.api.routers.toners import router as toner_router
from toner_api.api.routers.users import router as users_router

__all__ = [
    "auth_router",
    "config_router",
    "equipment_router",
    "os_router",
    "toner_router",
    "users_router",
]