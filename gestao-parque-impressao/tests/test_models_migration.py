from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from toner_api.models import HorarioFuncionamento, SlaConfig


def test_initial_migration_creates_schema_and_default_sla(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        table_names = set(inspect(connection).get_table_names())
        sla_rows = connection.execute(select(SlaConfig.__table__)).mappings().all()
        workday_rows = connection.execute(select(HorarioFuncionamento.__table__)).mappings().all()

    assert {
        "usuarios",
        "equipamentos",
        "ordens_servico",
        "sla_config",
        "horarios_funcionamento",
        "feriados",
        "toners",
        "lotes_toner",
        "movimentacoes_toner",
        "historico_os",
    }.issubset(table_names)
    assert {row["prioridade"] for row in sla_rows} == {"BAIXA", "MEDIA", "ALTA", "CRITICA"}
    assert len(workday_rows) == 5
    assert all(str(row["hora_inicio"]) == "08:00:00" for row in workday_rows)

    engine.dispose()