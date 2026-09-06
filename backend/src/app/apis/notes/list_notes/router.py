from app.deps import Owner, Repo
from app.models import Note
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.get("/notes", operation_id="list_notes", status_code=200)
def list_notes(owner: Owner, repo: Repo) -> list[Note]:
    try:
        with repo.transaction() as session:
            rows = functions.select_notes(owner, session)
            sections = functions.select_sections(owner, session)
            tasks = functions.select_tasks(owner, session)
            return functions.response(rows, sections, tasks)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
