from app.deps import Owner, Repo
from app.models import Note, NoteInput
from app.observability import ObservedRoute
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.post("/notes", operation_id="create_note", status_code=201)
def create_note(data: NoteInput, owner: Owner, repo: Repo) -> Note:
    return functions.execute(data, owner, repo)
