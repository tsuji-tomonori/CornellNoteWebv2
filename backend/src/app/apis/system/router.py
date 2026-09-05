from app.auth import local_login
from app.models import Login, Token
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health", operation_id="health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/local", operation_id="local_login")
def login(data: Login) -> Token:
    return local_login(data)
