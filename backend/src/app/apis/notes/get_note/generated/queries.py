# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import date, datetime
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
    version: int
    updated_at: datetime


def select_note(session: QuerySession, params: SelectNoteParams) -> list[SelectNoteRow]:
    """閲覧条件を満たすノートの基本情報を取得する"""
    return [
        SelectNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_select_note.sql", params.model_dump())
    ]


class SelectSectionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


class SelectSectionsRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID
    kind: str
    body: str


def select_sections(session: QuerySession, params: SelectSectionsParams) -> list[SelectSectionsRow]:
    """閲覧可能なノートの問い・本文・要約を取得する"""
    return [
        SelectSectionsRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "002_select_sections.sql", params.model_dump())
    ]


class SelectTasksParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


class SelectTasksRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID
    id: UUID
    text: str
    done: bool
    due: date | None


def select_tasks(session: QuerySession, params: SelectTasksParams) -> list[SelectTasksRow]:
    """閲覧可能なノートのタスクを表示順に取得する"""
    return [
        SelectTasksRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "003_select_tasks.sql", params.model_dump())
    ]
