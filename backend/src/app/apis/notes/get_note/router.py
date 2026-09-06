from uuid import UUID

from app.deps import Owner, Repo
from app.models import Note
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.get("/notes/{note_id}", operation_id="get_note", status_code=200)
def get_note(note_id: UUID, owner: Owner, repo: Repo) -> Note:
    try:
        with repo.transaction() as session:
            rows = functions.select_note(note_id, owner, session)
            if not rows:
                raise HTTPException(404, "ノートが見つかりません")
            sections = functions.select_sections(note_id, owner, session)
            tasks = functions.select_tasks(note_id, owner, session)
            return functions.response(rows, sections, tasks)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
