from app.deps import Repo
from app.models import Note
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api")


@router.get("/shared/{token}", operation_id="get_shared", status_code=200)
def get_shared(token: str, repo: Repo) -> Note:
    return functions.execute(token, repo)
