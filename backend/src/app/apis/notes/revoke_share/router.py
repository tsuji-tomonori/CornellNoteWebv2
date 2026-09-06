from uuid import UUID

from app.deps import Owner, Repo
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.delete("/notes/{note_id}/share", operation_id="revoke_share", status_code=204)
def revoke_share(note_id: UUID, owner: Owner, repo: Repo) -> None:
    try:
        with repo.transaction() as session:
            owned = functions.find(note_id, owner, session)
            if not owned:
                return None
            return functions.remove(note_id, session)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
