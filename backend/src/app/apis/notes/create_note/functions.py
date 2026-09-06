import json
from datetime import UTC, datetime
from uuid import uuid4

from app.models import Note, NoteInput
from app.port import Database

from .generated import queries


def execute(data: NoteInput, owner: str, repo: Database) -> Note:
    """初版のノートを保存する。"""
    note_id = uuid4()
    now = datetime.now(UTC)
    params = queries.InsertNoteParams(
        id=note_id,
        owner_id=owner,
        title=data.title,
        group_name=data.group,
        cue=data.cue,
        content=data.content,
        summary=data.summary,
        tasks=json.dumps([t.model_dump(mode="json") for t in data.tasks]),
        updated_at=now,
    )
    with repo.transaction() as session:
        queries.insert_note(session, params)
    return Note(**data.model_dump(), id=note_id, version=1, updated_at=now)
