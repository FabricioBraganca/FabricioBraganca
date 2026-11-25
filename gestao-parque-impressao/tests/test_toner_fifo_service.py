from datetime import date, datetime, timezone
from collections.abc import Iterator
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from toner_api.core.errors import ConflictError
from toner_api.db.base import Base
from toner_api.models.enums import CorToner, Perfil, TipoMovimentacao
from toner_api.models.toners import LoteToner, MovimentacaoToner, Toner
from toner_api.models.users import Usuario
from toner_api.services.toner_fifo_service import consumir_fifo


@pytest.fixture
def inventory_session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def create_inventory(session: Session, batches: list[tuple[str, int, date | None]]) -> tuple[UUID, UUID, list[UUID]]:
    user = Usuario(nome="Técnico", email="tecnico@example.com", senha_hash="hash", perfil=Perfil.TECNICO)
    toner = Toner(modelo="TN-100", cor=CorToner.PRETO, compatibilidade=["Laser 100"], estoque_minimo=1)
    session.add_all([user, toner])
    session.flush()
    lot_ids: list[UUID] = []
    for index, (batch_number, quantity, expiry) in enumerate(batches):
        lot = LoteToner(
            toner_id=toner.id,
            numero_lote=batch_number,
            data_entrada=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
            quantidade_inicial=quantity,
            quantidade_atual=quantity,
            validade=expiry,
        )
        session.add(lot)
        session.flush()
        lot_ids.append(lot.id)
    session.flush()
    return toner.id, user.id, lot_ids


def test_fifo_splits_consumption_between_oldest_lots(inventory_session: Session) -> None:
    toner_id, user_id, lot_ids = create_inventory(inventory_session, [("L1", 5, None), ("L2", 4, None)])

    movements = consumir_fifo(inventory_session, toner_id, 7, user_id, hoje=date(2026, 2, 1))

    assert [(movement.lote_id, movement.quantidade, movement.tipo) for movement in movements] == [
        (lot_ids[0], 5, TipoMovimentacao.SAIDA),
        (lot_ids[1], 2, TipoMovimentacao.SAIDA),
    ]
    balances = inventory_session.scalars(select(LoteToner.quantidade_atual).order_by(LoteToner.data_entrada)).all()
    assert balances == [0, 2]


def test_insufficient_fifo_stock_is_conflict_without_partial_changes(inventory_session: Session) -> None:
    toner_id, user_id, _ = create_inventory(inventory_session, [("L1", 3, None)])

    with pytest.raises(ConflictError, match=r"3 unidade\(s\) válida\(s\)"):
        consumir_fifo(inventory_session, toner_id, 4, user_id, hoje=date(2026, 2, 1))

    assert inventory_session.scalar(select(LoteToner.quantidade_atual)) == 3
    assert inventory_session.scalar(select(MovimentacaoToner.id)) is None


def test_expired_lots_cannot_be_consumed(inventory_session: Session) -> None:
    toner_id, user_id, _ = create_inventory(inventory_session, [("L1", 2, date(2026, 1, 31))])

    with pytest.raises(ConflictError, match=r"lote\(s\) vencido\(s\)"):
        consumir_fifo(inventory_session, toner_id, 1, user_id, hoje=date(2026, 2, 1))

    assert inventory_session.scalar(select(LoteToner.quantidade_atual)) == 2
    assert inventory_session.scalar(select(MovimentacaoToner.id)) is None