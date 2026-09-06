# Generated from sibling sql/*.sql and migration DDL. Do not edit.
from pathlib import Path
from uuid import UUID

from app.port import QuerySession
from pydantic import BaseModel, ConfigDict

SQL_DIR = Path(__file__).parents[1] / "sql"


class RevokeShareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    owner_id: str


def revoke_share(session: QuerySession, params: RevokeShareParams) -> None:
    """所有者のノートの共有を失効させる"""
    session.execute(SQL_DIR / "001_revoke_share.sql", params.model_dump())
