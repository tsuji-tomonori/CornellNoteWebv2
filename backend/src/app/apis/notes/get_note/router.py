from uuid import UUID

from app.deps import Owner, Repo
from app.models import Note
from app.observability import ObservedRoute
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.get("/notes/{note_id}", operation_id="get_note", status_code=200)
def get_note(note_id: UUID, owner: Owner, repo: Repo) -> Note:
    return functions.execute(note_id, owner, repo)
