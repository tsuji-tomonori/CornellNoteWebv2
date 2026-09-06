# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class UpdateShareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str
    share_expires: datetime | None
    share_hash: str | None


class UpdateShareRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID


def update_share(session: QuerySession, params: UpdateShareParams) -> list[UpdateShareRow]:
    """所有者のノートに期限付き共有を発行する"""
    return [
        UpdateShareRow.model_validate(row)
        for row in session.fetch_all(SQL_DIR / "001_update_share.sql", params.model_dump())
    ]
