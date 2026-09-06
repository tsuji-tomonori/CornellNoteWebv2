# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class InsertUserParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    created_at: datetime
    id: str


def insert_user(session: QuerySession, params: InsertUserParams) -> None:
    """認証済み所有者を初回のみ登録する"""
    session.execute(SQL_DIR / "001_insert_user.sql", params.model_dump())


class InsertNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_name: str
    id: UUID
    owner_id: str
    title: str
    updated_at: datetime


class InsertNoteRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    group_name: str
    version: int
    updated_at: datetime


def insert_note(session: QuerySession, params: InsertNoteParams) -> list[InsertNoteRow]:
    """ノートの基本情報を保存する"""
    return [
        InsertNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "002_insert_note.sql", params.model_dump())
    ]


class InsertSectionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str
    kind: str
    note_id: UUID
    updated_at: datetime


def insert_section(session: QuerySession, params: InsertSectionParams) -> None:
    """問い・本文・要約をそれぞれ一行として保存する"""
    session.execute(SQL_DIR / "003_insert_section.sql", params.model_dump())


class InsertTaskParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    done: bool
    due: date | None
    id: UUID
    note_id: UUID
    position: int
    text: str


def insert_task(session: QuerySession, params: InsertTaskParams) -> None:
    """個別タスクの内容・完了状態・期日・表示順序を保存する"""
    session.execute(SQL_DIR / "004_insert_task.sql", params.model_dump())
