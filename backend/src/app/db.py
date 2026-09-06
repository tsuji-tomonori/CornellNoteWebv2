from collections.abc import Generator, Mapping
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import certifi
import psycopg
from psycopg import sql
from psycopg.errors import SerializationFailure
from psycopg.rows import dict_row

from app.auth import settings
from app.port import Database, QuerySession, UpdateConflict


def connect(*, admin: bool = False) -> psycopg.Connection[dict[str, Any]]:
    cfg = settings()
    if cfg.dsql_host:
        from app.dsql import auth_token

        return psycopg.Connection[dict[str, Any]].connect(
            host=cfg.dsql_host,
            dbname="postgres",
            user="admin" if admin else "cornell_app",
            password=auth_token(admin),
            sslmode="verify-full",
            sslrootcert=certifi.where(),
            connect_timeout=10,
            row_factory=dict_row,
            prepare_threshold=None,
        )
    if not cfg.database_url:
        raise RuntimeError("DATABASE_URL or DSQL_HOST is required")
    return psycopg.Connection[dict[str, Any]].connect(
        cfg.database_url, row_factory=dict_row, connect_timeout=10, prepare_threshold=None
    )


class PostgresSession:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self.conn = conn

    def fetch_all(self, sql_path: Path, params: Mapping[str, object]) -> list[Mapping[str, object]]:
        return list(self.conn.execute(load_query(sql_path), params).fetchall())

    def execute(self, sql_path: Path, params: Mapping[str, object]) -> None:
        self.conn.execute(load_query(sql_path), params)


class PostgresDatabase:
    @contextmanager
    def transaction(self) -> Generator[QuerySession, None, None]:
        try:
            with connect() as conn:
                conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                yield PostgresSession(conn)
        except SerializationFailure as exc:
            raise UpdateConflict from exc


def database() -> Database:
    return PostgresDatabase()


@lru_cache
def load_query(path: Path) -> sql.SQL:
    return sql.SQL(path.read_text())  # pyright: ignore[reportArgumentType] - trusted packaged SQL; parameters remain bound
