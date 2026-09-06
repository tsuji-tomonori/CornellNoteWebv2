# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class SelectNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


class SelectNoteRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    group_name: str
    cue: str
    content: str
    summary: str
    tasks: str
    version: int
    updated_at: datetime


def select_note(session: QuerySession, params: SelectNoteParams) -> list[SelectNoteRow]:
    """所有者とIDでノートを取得する"""
    return [
        SelectNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_select_note.sql", params.model_dump())
    ]
