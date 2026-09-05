from app.deps import Owner, Repo
from app.models import Note
from fastapi import APIRouter

from . import functions

router = APIRouter(prefix="/api")


@router.get("/notes", operation_id="list_notes", status_code=200)
def list_notes(owner: Owner, repo: Repo) -> list[Note]:
    return functions.execute(owner, repo)
