from collections.abc import Iterator
from datetime import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from toner_api.api.dependencies import get_current_user
from toner_api.db.base import Base
from toner_api.db.session import get_db
from toner_api.main import app
from toner_api.core.security import hash_password
from toner_api.models.enums import PapelNoParque, Perfil, Prioridade, StatusOperacional, TipoEquipamento
from toner_api.models.equipment import Equipamento
from toner_api.models.sla import HorarioFuncionamento, SlaConfig
from toner_api.models.users import Usuario


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, dict[str, UUID]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory.begin() as session:
        password_hash = hash_password("Senha-forte-123!")
        user_data = (
            ("admin", "admin@example.com", Perfil.ADMIN),
            ("technician", "tech@example.com", Perfil.TECNICO),
            ("requester_a", "requester-a@example.com", Perfil.SOLICITANTE),
            ("requester_b", "requester-b@example.com", Perfil.SOLICITANTE),
        )
        users: dict[str, Usuario] = {}
        for name, email, role in user_data:
            user = Usuario(nome=name, email=email, senha_hash=password_hash, perfil=role, ativo=True)
            session.add(user)
            session.flush()
            users[name] = user
        session.add_all(
            [
                SlaConfig(
                    prioridade=priority,
                    horas_limite_resposta=response_hours,
                    horas_limite_resolucao=resolution_hours,
                    considera_horas_uteis=True,
                    ativo=True,
                )
                for priority, response_hours, resolution_hours in (
                    (Prioridade.BAIXA, 24, 72),
                    (Prioridade.MEDIA, 8, 48),
                    (Prioridade.ALTA, 4, 24),
                    (Prioridade.CRITICA, 1, 8),
                )
            ]
            + [
                HorarioFuncionamento(
                    dia_semana=weekday,
                    hora_inicio=time(8),
                    hora_fim=time(18),
                    ativo=True,
                )
                for weekday in range(5)
            ]
        )
        session.flush()
        primary = Equipamento(
            tipo=TipoEquipamento.IMPRESSORA,
            patrimonio="PAT-100",
            numero_serie="SN-100",
            marca="Fabricante",
            modelo="Laser 100",
            localizacao="TI / sala 1",
            responsavel_id=users["requester_a"].id,
            status_operacional=StatusOperacional.ATIVO,
            papel_no_parque=PapelNoParque.EM_USO,
            modelo_toner_compativel="TN-100",
            contador_paginas=100,
            ip_rede="10.0.0.10",
        )
        backup = Equipamento(
            tipo=TipoEquipamento.IMPRESSORA,
            patrimonio="PAT-101",
            numero_serie="SN-101",
            marca="Fabricante",
            modelo="Laser 101",
            localizacao="TI / sala 1",
            responsavel_id=users["requester_a"].id,
            status_operacional=StatusOperacional.ATIVO,
            papel_no_parque=PapelNoParque.BACKUP,
            modelo_toner_compativel="TN-100",
            contador_paginas=0,
            ip_rede="10.0.0.11",
        )
        session.add_all([primary, backup])
        session.flush()
        ids = {
            **{name: user.id for name, user in users.items()},
            "equipment_in_use": primary.id,
            "backup": backup.id,
        }

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        engine.dispose()


def authenticate(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "senha": "Senha-forte-123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_swagger_authorization_uses_bearer_token_not_password_form(
    api_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, _ids = api_client

    openapi = client.get("/openapi.json").json()
    security_schemes = openapi["components"]["securitySchemes"]

    assert security_schemes == {"HTTPBearer": {"type": "http", "scheme": "bearer"}}
    assert "application/json" in openapi["paths"]["/auth/login"]["post"]["requestBody"]["content"]


def open_order(client: TestClient, headers: dict[str, str], equipment_id: UUID) -> dict[str, object]:
    response = client.post(
        "/os",
        headers=headers,
        json={
            "equipamento_id": str(equipment_id),
            "tipo": "INSTALACAO",
            "prioridade": "MEDIA",
            "descricao_problema": "Instalar impressora de rede",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_requester_can_only_read_own_work_orders(api_client: tuple[TestClient, dict[str, UUID]]) -> None:
    client, ids = api_client
    requester_a = authenticate(client, "requester-a@example.com")
    requester_b = authenticate(client, "requester-b@example.com")
    own_order = open_order(client, requester_a, ids["equipment_in_use"])
    other_order = open_order(client, requester_b, ids["equipment_in_use"])

    own_response = client.get(f"/os/{own_order['id']}", headers=requester_a)
    private_response = client.get(f"/os/{other_order['id']}", headers=requester_a)
    list_response = client.get("/os", headers=requester_a)

    assert own_response.status_code == 200
    assert private_response.status_code == 404
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["solicitante_id"] == str(ids["requester_a"])


def test_technician_cannot_manage_users(api_client: tuple[TestClient, dict[str, UUID]]) -> None:
    client, _ids = api_client
    technician = authenticate(client, "tech@example.com")

    list_response = client.get("/usuarios", headers=technician)
    create_response = client.post(
        "/usuarios",
        headers=technician,
        json={
            "nome": "Novo usuário",
            "email": "novo@example.com",
            "senha": "Senha-forte-123!",
            "perfil": "SOLICITANTE",
        },
    )

    assert list_response.status_code == 403
    assert create_response.status_code == 403


def test_backup_promotion_demotes_current_equipment(api_client: tuple[TestClient, dict[str, UUID]]) -> None:
    client, ids = api_client
    technician = authenticate(client, "tech@example.com")

    response = client.post(f"/equipamentos/{ids['backup']}/promover-backup", headers=technician)
    previous = client.get(f"/equipamentos/{ids['equipment_in_use']}", headers=technician)

    assert response.status_code == 200, response.text
    assert response.json()["papel_no_parque"] == "EM_USO"
    assert previous.status_code == 200
    assert previous.json()["papel_no_parque"] == "BACKUP"


def test_fifo_http_consumes_lots_and_returns_conflict_when_short(api_client: tuple[TestClient, dict[str, UUID]]) -> None:
    client, _ids = api_client
    admin = authenticate(client, "admin@example.com")
    technician = authenticate(client, "tech@example.com")
    toner_response = client.post(
        "/toners",
        headers=admin,
        json={"modelo": "TN-200", "cor": "PRETO", "compatibilidade": ["Laser 200"], "estoque_minimo": 1},
    )
    assert toner_response.status_code == 201, toner_response.text
    toner_id = toner_response.json()["id"]
    lot_response = client.post(
        f"/toners/{toner_id}/lotes",
        headers=technician,
        json={"numero_lote": "LOTE-1", "quantidade": 3},
    )
    assert lot_response.status_code == 201, lot_response.text

    consumed = client.post(f"/toners/{toner_id}/consumir", headers=technician, json={"quantidade": 2})
    insufficient = client.post(f"/toners/{toner_id}/consumir", headers=technician, json={"quantidade": 2})
    fifo = client.get(f"/toners/{toner_id}/fifo", headers=technician)

    assert consumed.status_code == 200, consumed.text
    assert consumed.json()["movimentacoes"][0]["quantidade"] == 2
    assert insufficient.status_code == 409
    assert "1 unidade(s) válida(s) disponível(is)" in insufficient.json()["detail"]
    assert fifo.status_code == 200
    assert fifo.json()["items"][0]["quantidade_atual"] == 1


def test_os_workflow_pause_and_requester_reply(api_client: tuple[TestClient, dict[str, UUID]]) -> None:
    client, ids = api_client
    admin = authenticate(client, "admin@example.com")
    technician = authenticate(client, "tech@example.com")
    requester = authenticate(client, "requester-a@example.com")
    order = open_order(client, requester, ids["equipment_in_use"])

    assigned = client.patch(
        f"/os/{order['id']}/atribuir-tecnico",
        headers=admin,
        json={"tecnico_id": str(ids["technician"])},
    )
    started = client.patch(
        f"/os/{order['id']}/status", headers=technician, json={"status": "EM_ANDAMENTO"}
    )
    waiting = client.patch(
        f"/os/{order['id']}/status", headers=technician, json={"status": "AGUARDANDO_USUARIO"}
    )
    reply = client.patch(
        f"/os/{order['id']}", headers=requester, json={"resposta_solicitante": "Pode prosseguir."}
    )
    resumed = client.patch(
        f"/os/{order['id']}/status", headers=technician, json={"status": "EM_ANDAMENTO"}
    )

    assert assigned.status_code == 200, assigned.text
    assert started.status_code == 200, started.text
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["sla_status"] == "PAUSADO"
    assert reply.status_code == 200, reply.text
    assert "Pode prosseguir." in reply.json()["descricao_problema"]
    assert resumed.status_code == 200, resumed.text


def test_invalid_status_transition_maps_to_422(api_client: tuple[TestClient, dict[str, UUID]]) -> None:
    client, ids = api_client
    admin = authenticate(client, "admin@example.com")
    requester = authenticate(client, "requester-a@example.com")
    order = open_order(client, requester, ids["equipment_in_use"])

    response = client.patch(
        f"/os/{order['id']}/status",
        headers=admin,
        json={"status": "RESOLVIDA", "solucao_aplicada": "Resolvido"},
    )

    assert response.status_code == 422
    assert "não permitida" in response.json()["detail"]