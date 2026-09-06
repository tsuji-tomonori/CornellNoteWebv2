from app.deps import Owner, Repo
from app.models import TaskOverview
from app.observability import ObservedRoute
from app.port import UpdateConflict
from fastapi import APIRouter, HTTPException

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.get("/tasks", operation_id="list_tasks", status_code=200)
def list_tasks(owner: Owner, repo: Repo) -> list[TaskOverview]:
    try:
        with repo.transaction() as session:
            return functions.select(owner, session)
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
