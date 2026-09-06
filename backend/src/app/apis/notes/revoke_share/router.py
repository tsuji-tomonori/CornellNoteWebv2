from uuid import UUID

from app.deps import Owner, Repo
from app.observability import ObservedRoute
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.delete("/notes/{note_id}/share", operation_id="revoke_share", status_code=204)
def revoke_share(note_id: UUID, owner: Owner, repo: Repo) -> None:
    return functions.execute(note_id, owner, repo)
