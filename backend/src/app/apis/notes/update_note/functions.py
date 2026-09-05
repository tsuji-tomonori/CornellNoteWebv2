from uuid import UUID

from app.models import Note, NoteUpdate
from app.port import NoteStore


def execute(note_id: UUID, data: NoteUpdate, owner: str, repo: NoteStore) -> Note:
    return repo.update(owner, note_id, data)
