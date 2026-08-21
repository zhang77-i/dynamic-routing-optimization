from __future__ import annotations

from pathlib import Path

import duckdb

from .config import ProjectConfig
from .schema import DELIVERY_COLUMNS, ROAD_COLUMNS, duckdb_column_map


def _sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _render(template: str, config: ProjectConfig) -> str:
    replacements = {
        "{{DELIVERY_PATH}}": _sql_path(config.data["delivery"]),
        "{{ROADS_PATH}}": _sql_path(config.data["roads"]),
        "{{DELIVERY_COLUMNS}}": duckdb_column_map(DELIVERY_COLUMNS),
        "{{ROAD_COLUMNS}}": duckdb_column_map(ROAD_COLUMNS),
        "{{ORDER_CITY}}": str(config.processing["order_city"]).replace("'", "''"),
        "{{ROAD_CITY}}": str(config.processing["road_city"]).replace("'", "''"),
        "{{REFERENCE_YEAR}}": str(config.processing["reference_year"]),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def connect(config: ProjectConfig, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    database = config.data["database"]
    database.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database), read_only=read_only)


def execute_sql_file(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    config: ProjectConfig,
) -> None:
    sql = _render(path.read_text(encoding="utf-8"), config)
    for number, statement in enumerate(connection.extract_statements(sql), start=1):
        try:
            connection.execute(statement)
        except Exception as exc:
            raise RuntimeError(f"SQL failed in {path.name}, statement {number}") from exc


def build_database(config: ProjectConfig) -> None:
    scripts = [
        "01_create_raw_views.sql",
        "02_clean_delivery.sql",
        "03_clean_roads.sql",
        "04_create_audit_views.sql",
    ]
    with connect(config) as connection:
        connection.execute("SET threads = 4")
        connection.execute("SET preserve_insertion_order = false")
        for script in scripts:
            execute_sql_file(connection, config.root / "sql" / script, config)
        connection.execute("CHECKPOINT")
