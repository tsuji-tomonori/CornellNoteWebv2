from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Task(BaseModel):
    id: UUID
    text: str = Field(min_length=1, max_length=500)
    done: bool = False
    due: date | None = None


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    group: str = Field(default="未分類", min_length=1, max_length=80, pattern=r"\S")
    cue: str = Field(default="", max_length=20000)
    content: str = Field(default="", max_length=80000)
    summary: str = Field(default="", max_length=20000)
    tasks: list[Task] = Field(default_factory=list[Task], max_length=100)


class NoteUpdate(NoteInput):
    version: int = Field(ge=1)


class Note(NoteInput):
    id: UUID
    version: int
    updated_at: datetime


class Share(BaseModel):
    token: str
    expires_at: datetime


class Login(BaseModel):
    username: str = Field(pattern="^(alice|bob)$")
    password: str


class Token(BaseModel):
    access_token: str
