"""Cria o schema inicial e os valores padrão de SLA e expediente."""

from datetime import time
from uuid import uuid4

from alembic import op

from toner_api.db.base import Base
from toner_api.models import HorarioFuncionamento, SlaConfig

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Cria as tabelas da aplicação e carrega as configurações iniciais."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.bulk_insert(
        SlaConfig.__table__,
        [
            {
                "id": uuid4(),
                "prioridade": priority,
                "horas_limite_resposta": response_hours,
                "horas_limite_resolucao": resolution_hours,
                "considera_horas_uteis": True,
                "ativo": True,
            }
            for priority, response_hours, resolution_hours in (
                ("BAIXA", 24, 72),
                ("MEDIA", 8, 48),
                ("ALTA", 4, 24),
                ("CRITICA", 1, 8),
            )
        ],
    )
    op.bulk_insert(
        HorarioFuncionamento.__table__,
        [
            {
                "id": uuid4(),
                "dia_semana": weekday,
                "hora_inicio": time(8, 0),
                "hora_fim": time(18, 0),
                "ativo": True,
            }
            for weekday in range(5)
        ],
    )


def downgrade() -> None:
    """Remove o schema inicial criado pela revisão."""
    Base.metadata.drop_all(bind=op.get_bind())