# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class SelectSharedNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    share_expires: datetime | None
    share_hash: str | None


class SelectSharedNoteRow(BaseModel):
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


def select_shared_note(
    session: QuerySession, params: SelectSharedNoteParams
) -> list[SelectSharedNoteRow]:
    """ハッシュと期限が一致する共有ノートを取得する"""
    return [
        SelectSharedNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_select_shared_note.sql", params.model_dump())
    ]
