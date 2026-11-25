"""Ponto de entrada da aplicação FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from toner_api.api.exception_handlers import register_exception_handlers

from toner_api.api.routers import (
    auth_router,
    config_router,
    equipment_router,
    os_router,
    toner_router,
    users_router,
)
from toner_api.core.config import get_settings
from toner_api.core.logging_config import configure_logging

configure_logging()
settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(equipment_router)
app.include_router(os_router)
app.include_router(toner_router)
app.include_router(config_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Indica que o processo da API está respondendo."""
    return {"status": "ok"}