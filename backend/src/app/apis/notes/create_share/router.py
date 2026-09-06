from uuid import UUID

from app.deps import Owner, Repo
from app.models import Share
from app.observability import ObservedRoute
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.post("/notes/{note_id}/share", operation_id="create_share", status_code=200)
def create_share(note_id: UUID, owner: Owner, repo: Repo) -> Share:
    return functions.execute(note_id, owner, repo)
