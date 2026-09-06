# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class SelectOwnedNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


class SelectOwnedNoteRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    group_name: str
    version: int
    updated_at: datetime


def select_owned_note(
    session: QuerySession, params: SelectOwnedNoteParams
) -> list[SelectOwnedNoteRow]:
    """所有者に一致するノートと現在の版を確認する"""
    return [
        SelectOwnedNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_select_owned_note.sql", params.model_dump())
    ]


class UpdateNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_name: str
    id: UUID
    owner_id: str
    title: str
    updated_at: datetime
    version: int


class UpdateNoteRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    group_name: str
    version: int
    updated_at: datetime


def update_note(session: QuerySession, params: UpdateNoteParams) -> list[UpdateNoteRow]:
    """所有者と版が一致するときだけ基本情報を更新する"""
    return [
        UpdateNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "002_update_note.sql", params.model_dump())
    ]


class DeleteSectionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID


def delete_sections(session: QuerySession, params: DeleteSectionsParams) -> None:
    """同一トランザクション内で保存対象の記入欄を置き換える"""
    session.execute(SQL_DIR / "003_delete_sections.sql", params.model_dump())


class DeleteTasksParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID


def delete_tasks(session: QuerySession, params: DeleteTasksParams) -> None:
    """同一トランザクション内で保存対象のタスクを置き換える"""
    session.execute(SQL_DIR / "004_delete_tasks.sql", params.model_dump())


class InsertSectionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str
    kind: str
    note_id: UUID
    updated_at: datetime


def insert_section(session: QuerySession, params: InsertSectionParams) -> None:
    """問い・本文・要約をそれぞれ一行として保存する"""
    session.execute(SQL_DIR / "005_insert_section.sql", params.model_dump())


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
    session.execute(SQL_DIR / "006_insert_task.sql", params.model_dump())
