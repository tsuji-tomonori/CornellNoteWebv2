from uuid import UUID

from app.models import Note
from app.port import NoteStore


def execute(note_id: UUID, owner: str, repo: NoteStore) -> Note:
    return repo.get(owner, note_id)
