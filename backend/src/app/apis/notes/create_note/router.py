from app.deps import Owner, Repo
from app.models import Note, NoteInput
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api")


@router.post("/notes", operation_id="create_note", status_code=201)
def create_note(data: NoteInput, owner: Owner, repo: Repo) -> Note:
    return functions.execute(data, owner, repo)
