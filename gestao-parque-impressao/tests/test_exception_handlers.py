from fastapi import FastAPI
from fastapi.testclient import TestClient

from toner_api.api.exception_handlers import register_exception_handlers
from toner_api.core.errors import BusinessRuleError, ConflictError, NotFoundError


def create_error_app() -> FastAPI:
    application = FastAPI()
    register_exception_handlers(application)

    @application.get("/business")
    def business_error() -> None:
        raise BusinessRuleError("Regra inválida.")

    @application.get("/missing")
    def not_found_error() -> None:
        raise NotFoundError("Não encontrado.")

    @application.get("/conflict")
    def conflict_error() -> None:
        raise ConflictError("Conflito.")

    return application


def test_domain_errors_map_to_expected_http_statuses() -> None:
    with TestClient(create_error_app()) as client:
        business = client.get("/business")
        missing = client.get("/missing")
        conflict = client.get("/conflict")

    assert (business.status_code, business.json()["detail"]) == (422, "Regra inválida.")
    assert (missing.status_code, missing.json()["detail"]) == (404, "Não encontrado.")
    assert (conflict.status_code, conflict.json()["detail"]) == (409, "Conflito.")