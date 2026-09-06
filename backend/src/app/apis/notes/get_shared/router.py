from app.deps import Repo
from app.models import Note
from app.observability import ObservedRoute
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api", route_class=ObservedRoute)


@router.get("/shared/{token}", operation_id="get_shared", status_code=200)
def get_shared(token: str, repo: Repo) -> Note:
    return functions.execute(token, repo)
