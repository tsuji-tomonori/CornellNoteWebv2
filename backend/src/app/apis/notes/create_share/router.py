from uuid import UUID

from app.deps import Owner, Repo
from app.models import Share
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.post("/notes/{note_id}/share", operation_id="create_share", status_code=200)
def create_share(note_id: UUID, owner: Owner, repo: Repo) -> Share:
    try:
        with repo.transaction() as session:
            owned = functions.find(note_id, owner, session)
            if not owned:
                raise HTTPException(404, "ノートが見つかりません")
            share = functions.issue()
            functions.remove(note_id, session)
            return functions.save(note_id, share, owner, session)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
