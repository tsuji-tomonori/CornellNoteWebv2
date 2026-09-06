import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql

from app.models import NoteInput, Task


def split_notes(conn: psycopg.Connection[dict[str, Any]], directory: Path) -> None:
    def run(name: str, params: dict[str, Any]) -> psycopg.Cursor[dict[str, Any]]:
        return conn.execute(sql.SQL((directory / name).read_text()), params)  # pyright: ignore[reportArgumentType]

    after = UUID(int=0)
    while True:
        with conn.transaction():
            row = run("001_select_legacy.sql", {"after_id": after}).fetchone()
            if row is None:
                break
            data = NoteInput.model_validate(
                {
                    "title": row["title"],
                    "group": row["group_name"],
                    "cue": row["cue"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "tasks": json.loads(row["tasks"]),
                }
            )
            params = {"note_id": row["id"]}
            existing = run("006_select_sections.sql", params).fetchall()
            if not existing:
                run("002_insert_user.sql", {"id": row["owner_id"], "created_at": datetime.now(UTC)})
                for kind in ("cue", "content", "summary"):
                    run(
                        "003_insert_section.sql",
                        {
                            **params,
                            "kind": kind,
                            "body": getattr(data, kind),
                            "updated_at": row["updated_at"],
                        },
                    )
                for position, task in enumerate(data.tasks):
                    run(
                        "004_insert_task.sql", {**params, **task.model_dump(), "position": position}
                    )
                if row["share_hash"] is not None:
                    run(
                        "005_insert_share.sql",
                        {
                            **params,
                            "token_hash": row["share_hash"],
                            "expires_at": row["share_expires"],
                            "created_by": row["owner_id"],
                        },
                    )
            sections = {
                s["kind"]: s["body"] for s in run("006_select_sections.sql", params).fetchall()
            }
            tasks = [Task.model_validate(t) for t in run("007_select_tasks.sql", params).fetchall()]
            shares = run("008_select_share.sql", params).fetchall()
            expected_shares = (
                []
                if row["share_hash"] is None
                else [
                    {
                        "token_hash": row["share_hash"],
                        "expires_at": row["share_expires"],
                        "created_by": row["owner_id"],
                    }
                ]
            )
            if (
                sections != {k: getattr(data, k) for k in ("cue", "content", "summary")}
                or tasks != data.tasks
                or shares != expected_shares
            ):
                raise ValueError("移行先が元データと一致しません。旧カラムは削除しません")
            after = row["id"]
