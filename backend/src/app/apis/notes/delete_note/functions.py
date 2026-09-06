from uuid import UUID

from app.port import Database

from .generated import queries


def execute(note_id: UUID, owner: str, repo: Database) -> None:
    """本人のノートを冪等に削除する。"""
    with repo.transaction() as session:
        queries.delete_note(session, queries.DeleteNoteParams(id=note_id, owner_id=owner))
