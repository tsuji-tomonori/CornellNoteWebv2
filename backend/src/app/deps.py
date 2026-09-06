from typing import Annotated

from fastapi import Depends

from app.auth import authenticate
from app.db import database
from app.port import Database

Owner = Annotated[str, Depends(authenticate)]
Repo = Annotated[Database, Depends(database)]
