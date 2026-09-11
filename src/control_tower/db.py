from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd

from .config import DEFAULT_DB_PATH, SCHEMA_PATH


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(db_path: str | Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH, *, reset: bool = False) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with transaction(path) as connection:
        connection.executescript(schema)
    return path


def read_frame(query: str, params: tuple | dict = (), db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    connection = connect(db_path)
    try:
        return pd.read_sql_query(query, connection, params=params)
    finally:
        connection.close()


def table_count(table: str, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    allowed = {
        "zones", "partners", "missions", "mission_offers", "assignments", "availability",
        "partner_score_snapshots", "coverage_snapshots", "alerts", "quality_assessments",
    }
    if table not in allowed:
        raise ValueError(f"Unsupported table: {table}")
    connection = connect(db_path)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def database_ready(db_path: str | Path = DEFAULT_DB_PATH) -> bool:
    path = Path(db_path)
    if not path.exists():
        return False
    try:
        return table_count("missions", path) > 0
    except sqlite3.DatabaseError:
        return False
