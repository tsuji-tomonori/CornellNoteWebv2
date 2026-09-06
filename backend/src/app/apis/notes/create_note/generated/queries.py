# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class InsertNoteParams(BaseModel):
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


def insert_note(session: QuerySession, params: InsertNoteParams) -> None:
    """所有者に紐づく新しいノートを保存する"""
    session.execute(SQL_DIR / "001_insert_note.sql", params.model_dump())
