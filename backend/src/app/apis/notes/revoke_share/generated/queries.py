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


class DeleteShareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: UUID


def delete_share(session: QuerySession, params: DeleteShareParams) -> None:
    """所有者が指定した閲覧リンクを失効する"""
    session.execute(SQL_DIR / "002_delete_share.sql", params.model_dump())
