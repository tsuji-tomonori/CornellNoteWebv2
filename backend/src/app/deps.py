from typing import Annotated

from fastapi import Depends

from app.auth import authenticate
from app.port import NoteStore
from app.repository import store

Owner = Annotated[str, Depends(authenticate)]
Repo = Annotated[NoteStore, Depends(store)]
