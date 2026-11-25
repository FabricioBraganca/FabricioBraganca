"""Mapeamento global de exceções de domínio e persistência para HTTP."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from toner_api.core.errors import BusinessRuleError, ConflictError, NotFoundError

logger = logging.getLogger("toner_api.errors")


def register_exception_handlers(application: FastAPI) -> None:
    """Registra respostas seguras para erros esperados e falhas internas."""

    @application.exception_handler(BusinessRuleError)
    async def business_rule_error_handler(_request: Request, error: BusinessRuleError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @application.exception_handler(NotFoundError)
    async def not_found_error_handler(_request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @application.exception_handler(ConflictError)
    async def conflict_error_handler(_request: Request, error: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(IntegrityError)
    async def integrity_error_handler(_request: Request, _error: IntegrityError) -> JSONResponse:
        logger.info("database_integrity_conflict")
        return JSONResponse(status_code=409, content={"detail": "Conflito de integridade dos dados."})

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(_request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.exception("database_operation_failed", exc_info=error)
        return JSONResponse(status_code=500, content={"detail": "Erro interno ao acessar os dados."})

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, error: Exception) -> JSONResponse:
        logger.exception("unexpected_application_error", exc_info=error)
        return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."})