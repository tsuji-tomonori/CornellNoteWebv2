from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.auth import settings


def connect(*, admin: bool = False) -> psycopg.Connection[dict[str, Any]]:
    cfg = settings()
    if cfg.dsql_host:
        from app.dsql import auth_token

        return psycopg.connect(
            host=cfg.dsql_host,
            dbname="postgres",
            user="admin" if admin else "cornell_app",
            password=auth_token(admin),
            sslmode="verify-full",
            connect_timeout=10,
            row_factory=dict_row,
        )
    if not cfg.database_url:
        raise RuntimeError("DATABASE_URL or DSQL_HOST is required")
    return psycopg.connect(cfg.database_url, row_factory=dict_row, connect_timeout=10)
