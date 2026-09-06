from uuid import UUID

from app.deps import Owner, Repo
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.delete("/notes/{note_id}", operation_id="delete_note", status_code=204)
def delete_note(note_id: UUID, owner: Owner, repo: Repo) -> None:
    try:
        with repo.transaction() as session:
            owned = functions.find(note_id, owner, session)
            if not owned:
                return None
            functions.remove_children(note_id, session)
            return functions.remove(note_id, owner, session)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
