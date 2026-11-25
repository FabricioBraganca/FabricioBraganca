from fastapi.testclient import TestClient

from toner_api.core.config import Settings
from toner_api.main import app


def test_settings_support_postgresql_and_eight_hour_access_tokens() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.access_token_expire_minutes == 480
    assert settings.refresh_token_expire_days > 0


def test_health_endpoint_reports_api_availability() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_frontend_origin_passes_cors_preflight() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/os",
            headers={
                "Origin": "http://localhost:5500",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"