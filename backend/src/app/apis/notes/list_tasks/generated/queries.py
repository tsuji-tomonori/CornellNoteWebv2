# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import date
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class SelectTasksParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: str


class SelectTasksRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID
    id: UUID
    text: str
    done: bool
    due: date | None
    title: str
    group_name: str


def select_tasks(session: QuerySession, params: SelectTasksParams) -> list[SelectTasksRow]:
    """本人のノートに紐づくタスクを横断取得する"""
    return [
        SelectTasksRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_select_tasks.sql", params.model_dump())
    ]
