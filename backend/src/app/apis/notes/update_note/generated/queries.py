# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class UpdateNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    cue: str
    group_name: str
    id: UUID
    owner_id: str
    summary: str
    tasks: str
    title: str
    updated_at: datetime
    version: int


class UpdateNoteRow(BaseModel):
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


def update_note(session: QuerySession, params: UpdateNoteParams) -> list[UpdateNoteRow]:
    """所有者と版が一致するノートを更新する"""
    return [
        UpdateNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_update_note.sql", params.model_dump())
    ]


class SelectOwnedNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


class SelectOwnedNoteRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID


def select_owned_note(
    session: QuerySession, params: SelectOwnedNoteParams
) -> list[SelectOwnedNoteRow]:
    """更新失敗が権限不足か版競合かを区別する"""
    return [
        SelectOwnedNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "002_select_owned_note.sql", params.model_dump())
    ]
