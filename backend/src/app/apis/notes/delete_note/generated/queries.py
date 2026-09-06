# Generated from sibling sql/*.sql and migration DDL. Do not edit.
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


def select_owned_note(
    session: QuerySession, params: SelectOwnedNoteParams
) -> list[SelectOwnedNoteRow]:
    """操作対象ノートの所有者を確認する"""
    return [
        SelectOwnedNoteRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_select_owned_note.sql", params.model_dump())
    ]


class DeleteTasksParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID


def delete_tasks(session: QuerySession, params: DeleteTasksParams) -> None:
    """ノートに属する子データを削除する"""
    session.execute(SQL_DIR / "002_delete_tasks.sql", params.model_dump())


class DeleteSectionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID


def delete_sections(session: QuerySession, params: DeleteSectionsParams) -> None:
    """ノートに属する子データを削除する"""
    session.execute(SQL_DIR / "003_delete_sections.sql", params.model_dump())


class DeleteShareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID


def delete_share(session: QuerySession, params: DeleteShareParams) -> None:
    """ノートに属する子データを削除する"""
    session.execute(SQL_DIR / "004_delete_share.sql", params.model_dump())


class DeleteNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


def delete_note(session: QuerySession, params: DeleteNoteParams) -> None:
    """所有者に一致するノートの基本情報を最後に削除する"""
    session.execute(SQL_DIR / "005_delete_note.sql", params.model_dump())
