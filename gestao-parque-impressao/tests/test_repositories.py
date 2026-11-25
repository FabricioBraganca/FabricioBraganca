from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from toner_api.db.base import Base
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.repositories.users import UsuarioRepository


def test_user_repository_filters_and_paginates_with_total() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Usuario(nome="Ana", email="ana@example.com", senha_hash="hash", perfil=Perfil.TECNICO),
                Usuario(nome="Bia", email="bia@example.com", senha_hash="hash", perfil=Perfil.TECNICO),
                Usuario(nome="Caio", email="caio@example.com", senha_hash="hash", perfil=Perfil.ADMIN),
            ]
        )
        session.flush()

        users, total = UsuarioRepository(session).listar(limit=1, offset=1, perfil=Perfil.TECNICO)

        assert total == 2
        assert len(users) == 1
        assert users[0].nome == "Bia"
    engine.dispose()