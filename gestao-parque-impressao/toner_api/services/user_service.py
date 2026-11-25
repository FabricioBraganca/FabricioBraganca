"""Operações de usuários e autenticação da aplicação."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from toner_api.core.errors import BusinessRuleError, ConflictError, NotFoundError
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
from toner_api.repositories.users import UsuarioRepository
from toner_api.schemas.users import TokenPair, UsuarioCreate, UsuarioUpdate


class UsuarioService:
    """Coordena autenticação, autorização de usuário e mudanças de cadastro."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = UsuarioRepository(db)

    def autenticar(self, email: str, senha: str) -> TokenPair:
        """Valida credenciais e emite access token e refresh token."""
        usuario = self.repository.por_email(email.strip().casefold())
        if usuario is None or not usuario.ativo or not verify_password(senha, usuario.senha_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")
        return TokenPair(
            access_token=create_access_token(usuario.id),
            refresh_token=create_refresh_token(usuario.id),
        )

    def renovar_tokens(self, refresh_token: str) -> TokenPair:
        """Valida refresh token e rotaciona os tokens do usuário ativo."""
        try:
            usuario_id = decode_token(refresh_token, "refresh")
        except TokenValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido ou expirado.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from error
        usuario = self.repository.obter(usuario_id)
        if usuario is None or not usuario.ativo:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido ou inativo.")
        return TokenPair(
            access_token=create_access_token(usuario.id),
            refresh_token=create_refresh_token(usuario.id),
        )

    def criar(self, payload: UsuarioCreate) -> Usuario:
        """Cria conta ativa com e-mail normalizado e senha em hash."""
        email = str(payload.email).strip().casefold()
        if self.repository.por_email(email) is not None:
            raise ConflictError("Já existe usuário cadastrado com este e-mail.")
        usuario = Usuario(
            nome=payload.nome.strip(),
            email=email,
            senha_hash=hash_password(payload.senha),
            perfil=payload.perfil,
            setor=payload.setor.strip() if payload.setor else None,
            ativo=True,
        )
        return self.repository.adicionar(usuario)

    def listar(
        self,
        limit: int,
        offset: int,
        perfil: Perfil | None = None,
        setor: str | None = None,
        ativo: bool | None = None,
    ) -> tuple[list[Usuario], int]:
        return self.repository.listar(limit, offset, perfil, setor, ativo)

    def obter(self, usuario_id: UUID) -> Usuario:
        """Obtém usuário ou sinaliza recurso inexistente."""
        usuario = self.repository.obter(usuario_id)
        if usuario is None:
            raise NotFoundError("Usuário não encontrado.")
        return usuario

    def atualizar(self, usuario_id: UUID, payload: UsuarioUpdate) -> Usuario:
        """Atualiza campos informados, incluindo troca de senha ou perfil."""
        usuario = self.obter(usuario_id)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise BusinessRuleError("Informe ao menos um campo para atualizar.")
        if "email" in updates and updates["email"] is not None:
            email = str(updates["email"]).strip().casefold()
            duplicate = self.repository.por_email(email)
            if duplicate is not None and duplicate.id != usuario.id:
                raise ConflictError("Já existe usuário cadastrado com este e-mail.")
            updates["email"] = email
        if "nova_senha" in updates:
            new_password = updates.pop("nova_senha")
            if new_password is not None:
                updates["senha_hash"] = hash_password(new_password)
        for field in ("nome", "email", "perfil", "ativo"):
            if field in updates and updates[field] is None:
                raise BusinessRuleError(f"O campo '{field}' não pode ser nulo.")
        if "nome" in updates and updates["nome"] is not None:
            updates["nome"] = updates["nome"].strip()
        if "setor" in updates and updates["setor"] is not None:
            updates["setor"] = updates["setor"].strip()
        for field, value in updates.items():
            setattr(usuario, field, value)
        self.db.flush()
        return usuario

    def desativar(self, usuario_id: UUID) -> Usuario:
        """Desativa a conta sem remover referências históricas do usuário."""
        usuario = self.obter(usuario_id)
        usuario.ativo = False
        self.db.flush()
        return usuario