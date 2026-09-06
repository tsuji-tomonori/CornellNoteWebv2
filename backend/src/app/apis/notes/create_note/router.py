from app.deps import Owner, Repo
from app.models import Note, NoteInput
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.post("/notes", operation_id="create_note", status_code=201)
def create_note(data: NoteInput, owner: Owner, repo: Repo) -> Note:
    try:
        with repo.transaction() as session:
            functions.ensure_user(owner, session)
            row = functions.create(data, owner, session)
            functions.save_sections(row.id, data, session)
            functions.save_tasks(row.id, data, session)
            return functions.response(row, data)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
