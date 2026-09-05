from uuid import UUID

from app.port import NoteStore


def execute(note_id: UUID, owner: str, repo: NoteStore) -> None:
    return repo.revoke(owner, note_id)
