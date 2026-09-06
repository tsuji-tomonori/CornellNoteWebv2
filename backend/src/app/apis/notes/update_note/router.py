from uuid import UUID

from app.deps import Owner, Repo
from app.models import Note, NoteUpdate
from app.observability import ObservedRoute
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.put("/notes/{note_id}", operation_id="update_note", status_code=200)
def update_note(note_id: UUID, data: NoteUpdate, owner: Owner, repo: Repo) -> Note:
    return functions.execute(note_id, data, owner, repo)
