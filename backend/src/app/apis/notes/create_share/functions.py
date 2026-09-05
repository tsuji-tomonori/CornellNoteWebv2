from uuid import UUID

from app.models import Share
from app.port import NoteStore


def execute(note_id: UUID, owner: str, repo: NoteStore) -> Share:
    return repo.share(owner, note_id)
