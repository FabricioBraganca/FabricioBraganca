"""Comandos administrativos locais para provisionar o primeiro ADMIN."""

import argparse
from getpass import getpass

from sqlalchemy import func, select

from toner_api.db.session import SessionLocal
from toner_api.models.enums import Perfil
from toner_api.models.users import Usuario
from toner_api.schemas.users import UsuarioCreate
from toner_api.services.user_service import UsuarioService


def create_first_admin() -> int:
    """Cria o primeiro ADMIN solicitando a senha sem exibi-la no terminal."""
    nome = input("Nome do administrador: ").strip()
    email = input("E-mail do administrador: ").strip()
    password = getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass("Confirme a senha: ")
    if password != confirmation:
        print("As senhas não conferem.")
        return 1

    with SessionLocal.begin() as session:
        existing_admins = session.scalar(
            select(func.count()).select_from(Usuario).where(Usuario.perfil == Perfil.ADMIN)
        )
        if existing_admins:
            print("Já existe um ADMIN; use o endpoint administrativo para criar outros usuários.")
            return 1
        payload = UsuarioCreate(nome=nome, email=email, senha=password, perfil=Perfil.ADMIN)
        UsuarioService(session).criar(payload)
    print("Administrador inicial criado.")
    return 0


def main() -> None:
    """Executa o comando de provisionamento inicial."""
    parser = argparse.ArgumentParser(description="Provisionamento inicial da API")
    parser.add_argument("command", choices=("create-admin",))
    arguments = parser.parse_args()
    if arguments.command == "create-admin":
        raise SystemExit(create_first_admin())


if __name__ == "__main__":
    main()