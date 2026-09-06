# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class DeleteNoteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


def delete_note(session: QuerySession, params: DeleteNoteParams) -> None:
    """所有者に一致するノートだけを削除する"""
    session.execute(SQL_DIR / "001_delete_note.sql", params.model_dump())
