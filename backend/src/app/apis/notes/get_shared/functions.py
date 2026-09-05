from app.models import Note
from app.port import NoteStore


def execute(token: str, repo: NoteStore) -> Note:
    return repo.shared(token)
