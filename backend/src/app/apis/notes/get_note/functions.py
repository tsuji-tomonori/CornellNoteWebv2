from uuid import UUID

from app.models import Note
from app.note_mapping import decode
from app.port import Database
from fastapi import HTTPException

from .generated import queries


def execute(note_id: UUID, owner: str, repo: Database) -> Note:
    """所有者に一致するノートを返す。"""
    with repo.transaction() as session:
        rows = queries.select_note(session, queries.SelectNoteParams(id=note_id, owner_id=owner))
    if not rows:
        raise HTTPException(404, "ノートが見つかりません")
    return decode(rows[0])
