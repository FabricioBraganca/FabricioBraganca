"""Regras de negócio do inventário e da troca de equipamentos de backup."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toner_api.core.errors import BusinessRuleError, ConflictError, NotFoundError
from toner_api.models.enums import PapelNoParque, StatusOperacional, TipoEquipamento
from toner_api.models.equipment import Equipamento
from toner_api.models.users import Usuario
from toner_api.repositories.equipment import EquipamentoRepository
from toner_api.schemas.equipment import EquipamentoCreate, EquipamentoUpdate


class EquipamentoService:
    """Valida equipamentos, gerencia o parque e preserva OS históricas."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = EquipamentoRepository(db)

    @staticmethod
    def _validar_campos_por_tipo(data: dict[str, object], tipo: TipoEquipamento) -> None:
        printer_fields = ("modelo_toner_compativel", "contador_paginas", "ip_rede")
        computer_fields = ("hostname", "sistema_operacional", "memoria_ram_gb", "armazenamento_gb")
        required_fields = printer_fields if tipo == TipoEquipamento.IMPRESSORA else computer_fields
        forbidden_fields = computer_fields if tipo == TipoEquipamento.IMPRESSORA else printer_fields
        missing = [field for field in required_fields if data.get(field) is None]
        supplied_forbidden = [field for field in forbidden_fields if data.get(field) is not None]
        if missing or supplied_forbidden:
            details = []
            if missing:
                details.append(f"campos obrigatórios ausentes: {', '.join(missing)}")
            if supplied_forbidden:
                details.append(f"campos incompatíveis preenchidos: {', '.join(supplied_forbidden)}")
            raise BusinessRuleError(f"Dados inválidos para {tipo.value}: {'; '.join(details)}.")

    def _validar_responsavel(self, responsavel_id: UUID | None) -> None:
        if responsavel_id is not None:
            user = self.db.get(Usuario, responsavel_id)
            if user is None or not user.ativo:
                raise NotFoundError("Responsável não encontrado ou inativo.")

    def criar(self, payload: EquipamentoCreate) -> Equipamento:
        """Cria equipamento após validar campos específicos do discriminador."""
        data = payload.model_dump()
        self._validar_campos_por_tipo(data, payload.tipo)
        self._validar_responsavel(payload.responsavel_id)
        duplicate = self.db.scalar(
            select(Equipamento).where(
                (Equipamento.patrimonio == payload.patrimonio)
                | (Equipamento.numero_serie == payload.numero_serie)
            )
        )
        if duplicate is not None:
            raise ConflictError("Patrimônio ou número de série já cadastrado.")
        equipamento = Equipamento(**data)
        self.db.add(equipamento)
        self.db.flush()
        return equipamento

    def obter(self, equipamento_id: UUID) -> Equipamento:
        equipamento = self.repository.obter(equipamento_id)
        if equipamento is None:
            raise NotFoundError("Equipamento não encontrado.")
        return equipamento

    def listar(
        self,
        limit: int,
        offset: int,
        tipo: TipoEquipamento | None = None,
        status_operacional: StatusOperacional | None = None,
        papel_no_parque: PapelNoParque | None = None,
        localizacao: str | None = None,
        busca: str | None = None,
    ) -> tuple[list[Equipamento], int]:
        return self.repository.listar(limit, offset, tipo, status_operacional, papel_no_parque, localizacao, busca)

    def atualizar(self, equipamento_id: UUID, payload: EquipamentoUpdate) -> Equipamento:
        """Atualiza e revalida o conjunto completo conforme o tipo final."""
        equipamento = self.obter(equipamento_id)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise BusinessRuleError("Informe ao menos um campo para atualizar.")
        if (
            changes.get("papel_no_parque") == PapelNoParque.EM_USO
            and equipamento.papel_no_parque != PapelNoParque.EM_USO
        ):
            raise BusinessRuleError("Use o endpoint de promoção para colocar um equipamento EM_USO.")
        current = {column.key: getattr(equipamento, column.key) for column in Equipamento.__table__.columns}
        current.update(changes)
        for field in ("patrimonio", "numero_serie", "marca", "modelo", "localizacao", "tipo", "papel_no_parque"):
            if current[field] is None or (isinstance(current[field], str) and not current[field].strip()):
                raise BusinessRuleError(f"O campo '{field}' não pode ser nulo ou vazio.")
        self._validar_campos_por_tipo(current, current["tipo"])
        self._validar_responsavel(current["responsavel_id"])
        if "patrimonio" in changes or "numero_serie" in changes:
            duplicate = self.db.scalar(
                select(Equipamento).where(
                    Equipamento.id != equipamento_id,
                    (Equipamento.patrimonio == current["patrimonio"])
                    | (Equipamento.numero_serie == current["numero_serie"]),
                )
            )
            if duplicate is not None:
                raise ConflictError("Patrimônio ou número de série já cadastrado.")
        for field, value in changes.items():
            setattr(equipamento, field, value)
        self.db.flush()
        return equipamento

    def alterar_status(self, equipamento_id: UUID, status: StatusOperacional) -> Equipamento:
        """Permite ao técnico modificar somente o estado operacional do ativo."""
        equipamento = self.obter(equipamento_id)
        equipamento.status_operacional = status
        self.db.flush()
        return equipamento

    def promover_backup(self, equipamento_id: UUID) -> Equipamento:
        """Promove backup e rebaixa o equipamento em uso do mesmo grupo."""
        equipamento = self.db.scalar(
            select(Equipamento).where(Equipamento.id == equipamento_id).with_for_update()
        )
        if equipamento is None:
            raise NotFoundError("Equipamento não encontrado.")
        if equipamento.papel_no_parque != PapelNoParque.BACKUP:
            raise BusinessRuleError("Somente equipamento BACKUP pode ser promovido.")
        if equipamento.status_operacional != StatusOperacional.ATIVO:
            raise BusinessRuleError("Somente equipamento operacional ATIVO pode ser promovido.")
        antigos = self.repository.equipamentos_em_uso_no_grupo(equipamento)
        for antigo in antigos:
            antigo.papel_no_parque = PapelNoParque.BACKUP
        equipamento.papel_no_parque = PapelNoParque.EM_USO
        self.db.flush()
        return equipamento

    def parque(self) -> dict[str, object]:
        """Resume ocupação do parque e backups ativos disponíveis por tipo."""
        counts = self.repository.contar_por_papel()
        in_use = counts.get(PapelNoParque.EM_USO, 0)
        backups = counts.get(PapelNoParque.BACKUP, 0)
        total = in_use + backups
        available_rows = self.db.execute(
            select(Equipamento.tipo, func.count()).where(
                Equipamento.papel_no_parque == PapelNoParque.BACKUP,
                Equipamento.status_operacional == StatusOperacional.ATIVO,
            ).group_by(Equipamento.tipo)
        ).all()
        return {
            "total_em_uso": in_use,
            "total_backup": backups,
            "taxa_ocupacao": round(in_use / total * 100, 2) if total else 0.0,
            "backups_disponiveis_por_tipo": {tipo: count for tipo, count in available_rows},
        }

    def excluir(self, equipamento_id: UUID) -> Equipamento:
        """Descarta logicamente o ativo após bloquear OS ainda abertas."""
        equipamento = self.obter(equipamento_id)
        if self.repository.tem_os_aberta(equipamento_id):
            raise ConflictError("Não é possível excluir equipamento com OS aberta.")
        equipamento.status_operacional = StatusOperacional.DESCARTADO
        equipamento.papel_no_parque = PapelNoParque.BACKUP
        self.db.flush()
        return equipamento