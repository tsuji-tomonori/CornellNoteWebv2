import json
from datetime import UTC, datetime
from uuid import UUID

from app.models import Note, NoteUpdate
from app.note_mapping import decode
from app.port import Database, UpdateConflict
from fastapi import HTTPException

from .generated import queries


def execute(note_id: UUID, data: NoteUpdate, owner: str, repo: Database) -> Note:
    """所有者と版を確認し、競合時は変更せず返す。"""
    params = queries.UpdateNoteParams(
        id=note_id,
        owner_id=owner,
        title=data.title,
        group_name=data.group,
        cue=data.cue,
        content=data.content,
        summary=data.summary,
        tasks=json.dumps([t.model_dump(mode="json") for t in data.tasks]),
        updated_at=datetime.now(UTC),
        version=data.version,
    )
    try:
        with repo.transaction() as session:
            rows = queries.update_note(session, params)
        if not rows:
            with repo.transaction() as session:
                owned = queries.select_owned_note(
                    session, queries.SelectOwnedNoteParams(id=note_id, owner_id=owner)
                )
            if not owned:
                raise HTTPException(404, "ノートが見つかりません")
            raise HTTPException(
                409, "別の画面で更新されています。入力を控えて再読み込みしてください"
            )
        return decode(rows[0])
    except UpdateConflict as exc:
        raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc
