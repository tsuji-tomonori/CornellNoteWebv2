import hashlib
import os
from pathlib import Path

import sqlglot
from psycopg import sql

from app.auth import settings
from app.db import connect


def migrate() -> None:
    cfg = settings()
    with connect(admin=True) as conn:
        conn.autocommit = True
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name VARCHAR(200) PRIMARY KEY, checksum VARCHAR(64) NOT NULL)"
        )
        for path in sorted(Path(os.getenv("MIGRATIONS_DIR", "backend/migrations")).glob("*.sql")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            previous = conn.execute(
                "SELECT checksum FROM schema_migrations WHERE name=%s", (path.name,)
            ).fetchone()
            if previous:
                if previous["checksum"] != digest:
                    raise RuntimeError("Applied migration modified: " + path.name)
                continue
            for expression in sqlglot.parse(path.read_text(), dialect="postgres"):
                if expression is None:
                    continue
                statement = expression.sql(dialect="postgres")
                if cfg.dsql_host and statement.startswith("CREATE INDEX"):
                    statement = statement.replace("CREATE INDEX", "CREATE INDEX ASYNC", 1)
                    job = conn.execute(statement).fetchone()
                    if job:
                        conn.execute("SELECT sys.wait_for_job(%s)", (next(iter(job.values())),))
                else:
                    conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (name, checksum) VALUES (%s,%s)", (path.name, digest)
            )
        if cfg.dsql_host:
            if not conn.execute(
                "SELECT rolname FROM pg_roles WHERE rolname='cornell_app'"
            ).fetchone():
                conn.execute("CREATE ROLE cornell_app WITH LOGIN")
            conn.execute("GRANT USAGE ON SCHEMA public TO cornell_app")
            conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON notes TO cornell_app")
            conn.execute(
                sql.SQL("AWS IAM GRANT cornell_app TO {}").format(
                    sql.Literal(os.environ["APP_ROLE_ARN"])
                )
            )


if __name__ == "__main__":
    migrate()
