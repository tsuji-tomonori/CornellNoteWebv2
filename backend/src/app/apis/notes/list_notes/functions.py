from app.models import Note
from app.port import NoteStore


def execute(owner: str, repo: NoteStore) -> list[Note]:
    return repo.list_notes(owner)
