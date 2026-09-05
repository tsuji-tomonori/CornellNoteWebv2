from app.models import Note, NoteInput
from app.port import NoteStore


def execute(data: NoteInput, owner: str, repo: NoteStore) -> Note:
    return repo.create(owner, data)
