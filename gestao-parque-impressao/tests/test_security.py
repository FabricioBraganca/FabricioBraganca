from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from toner_api.api.dependencies import get_current_user, require_role
from toner_api.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario


def test_password_hash_verifies_without_storing_plaintext() -> None:
    password = "S3nh@-corporativa!"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("senha-errada", password_hash)


def test_access_and_refresh_tokens_are_distinct_types() -> None:
    user_id = uuid4()
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    assert decode_token(access_token, "access") == user_id
    assert decode_token(refresh_token, "refresh") == user_id
    with pytest.raises(TokenValidationError):
        decode_token(refresh_token, "access")


def test_role_dependency_denies_user_with_wrong_profile() -> None:
    application = FastAPI()
    technician = Usuario(nome="Técnico", email="tecnico@example.com", senha_hash="hash", perfil=Perfil.TECNICO)

    @application.get("/admin")
    def admin_endpoint(
        current_user: Annotated[Usuario, Depends(require_role(Perfil.ADMIN))],
    ) -> dict[str, str]:
        return {"perfil": current_user.perfil.value}

    def fake_current_user() -> Usuario:
        return technician

    application.dependency_overrides[get_current_user] = fake_current_user
    with TestClient(application) as client:
        response = client.get("/admin")

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissão insuficiente."