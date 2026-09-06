from app.models import Note
from app.note_mapping import decode
from app.port import Database

from .generated import queries


def execute(owner: str, repo: Database) -> list[Note]:
    """本人のノート一覧を取得する。"""
    with repo.transaction() as session:
        rows = queries.select_notes(session, queries.SelectNotesParams(owner_id=owner))
    return [decode(row) for row in rows]
