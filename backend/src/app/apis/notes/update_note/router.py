from uuid import UUID

from app.deps import Owner, Repo
from app.models import Note, NoteUpdate
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.put("/notes/{note_id}", operation_id="update_note", status_code=200)
def update_note(note_id: UUID, data: NoteUpdate, owner: Owner, repo: Repo) -> Note:
    try:
        with repo.transaction() as session:
            owned = functions.find(note_id, owner, session)
            if not owned:
                raise HTTPException(404, "ノートが見つかりません")
            rows = functions.update(note_id, data, owner, session)
            if not rows:
                raise HTTPException(
                    409, "別の画面で更新されています。入力を控えて再読み込みしてください"
                )
            functions.clear_children(note_id, session)
            functions.save_sections(note_id, data, session)
            functions.save_tasks(note_id, data, session)
            return functions.response(rows[0], data)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
