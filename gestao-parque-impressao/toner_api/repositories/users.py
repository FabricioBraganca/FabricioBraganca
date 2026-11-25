"""Consultas e persistência de usuários."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.repositories.common import paginar


class UsuarioRepository:
    """Acesso a usuários por identificador, e-mail e filtros paginados."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obter(self, usuario_id: UUID) -> Usuario | None:
        return self.db.get(Usuario, usuario_id)

    def por_email(self, email: str) -> Usuario | None:
        return self.db.scalar(select(Usuario).where(Usuario.email == email.casefold()))

    def listar(
        self,
        limit: int,
        offset: int,
        perfil: Perfil | None = None,
        setor: str | None = None,
        ativo: bool | None = None,
    ) -> tuple[list[Usuario], int]:
        statement = select(Usuario)
        if perfil is not None:
            statement = statement.where(Usuario.perfil == perfil)
        if setor is not None:
            statement = statement.where(Usuario.setor == setor)
        if ativo is not None:
            statement = statement.where(Usuario.ativo.is_(ativo))
        statement = statement.order_by(Usuario.nome, Usuario.id)
        return paginar(self.db, statement, limit, offset)

    def adicionar(self, usuario: Usuario) -> Usuario:
        self.db.add(usuario)
        self.db.flush()
        return usuario