from datetime import UTC, datetime

from app.deps import Repo
from app.models import Note
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.get("/shared/{token}", operation_id="get_shared", status_code=200)
def get_shared(token: str, repo: Repo) -> Note:
    try:
        with repo.transaction() as session:
            token_hash = functions.digest(token)
            expires_at = datetime.now(UTC)
            rows = functions.select_note(token_hash, expires_at, session)
            if not rows:
                raise HTTPException(404, "共有リンクが無効または期限切れです")
            sections = functions.select_sections(token_hash, expires_at, session)
            tasks = functions.select_tasks(token_hash, expires_at, session)
            return functions.response(rows, sections, tasks)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
