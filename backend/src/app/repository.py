import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from psycopg.errors import SerializationFailure

from app.db import connect
from app.models import Note, NoteInput, NoteUpdate, Share
from app.port import NoteStore


def decode(row: dict[str, object]) -> Note:
    value = dict(row)
    value["group"] = value.pop("group_name")
    value["tasks"] = json.loads(str(value["tasks"]))
    return Note.model_validate(value)


class PostgresStore:
    def list_notes(self, owner: str) -> list[Note]:
        with connect() as conn:
            return [
                decode(row)
                for row in conn.execute(
                    "SELECT id, title, group_name, cue, content, summary, tasks, version, updated_at FROM notes WHERE owner_id=%s ORDER BY updated_at DESC",
                    (owner,),
                ).fetchall()
            ]

    def create(self, owner: str, data: NoteInput) -> Note:
        note_id = uuid4()
        now = datetime.now(UTC)
        with connect() as conn:
            conn.execute(
                "INSERT INTO notes (id, owner_id, title, group_name, cue, content, summary, tasks, version, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s)",
                (
                    note_id,
                    owner,
                    data.title,
                    data.group,
                    data.cue,
                    data.content,
                    data.summary,
                    json.dumps([t.model_dump(mode="json") for t in data.tasks]),
                    now,
                ),
            )
        return Note(**data.model_dump(), id=note_id, version=1, updated_at=now)

    def get(self, owner: str, note_id: UUID) -> Note:
        with connect() as conn:
            row = conn.execute(
                "SELECT id, title, group_name, cue, content, summary, tasks, version, updated_at FROM notes WHERE id=%s AND owner_id=%s",
                (note_id, owner),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "ノートが見つかりません")
            return decode(row)

    def update(self, owner: str, note_id: UUID, data: NoteUpdate) -> Note:
        try:
            with connect() as conn:
                row = conn.execute(
                    "UPDATE notes SET title=%s, group_name=%s, cue=%s, content=%s, summary=%s, tasks=%s, version=version+1, updated_at=%s WHERE id=%s AND owner_id=%s AND version=%s RETURNING id, title, group_name, cue, content, summary, tasks, version, updated_at",
                    (
                        data.title,
                        data.group,
                        data.cue,
                        data.content,
                        data.summary,
                        json.dumps([t.model_dump(mode="json") for t in data.tasks]),
                        datetime.now(UTC),
                        note_id,
                        owner,
                        data.version,
                    ),
                ).fetchone()
                if row is None:
                    self.get(owner, note_id)
                    raise HTTPException(
                        409, "別の画面で更新されています。入力を控えて再読み込みしてください"
                    )
                result = decode(row)
            return result
        except SerializationFailure as exc:
            raise HTTPException(409, "更新が競合しました。再読み込みしてください") from exc

    def delete(self, owner: str, note_id: UUID) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM notes WHERE id=%s AND owner_id=%s", (note_id, owner))

    def share(self, owner: str, note_id: UUID) -> Share:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(days=7)
        with connect() as conn:
            row = conn.execute(
                "UPDATE notes SET share_hash=%s, share_expires=%s WHERE id=%s AND owner_id=%s RETURNING id",
                (hashlib.sha256(token.encode()).hexdigest(), expires, note_id, owner),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "ノートが見つかりません")
        return Share(token=token, expires_at=expires)

    def revoke(self, owner: str, note_id: UUID) -> None:
        with connect() as conn:
            conn.execute(
                "UPDATE notes SET share_hash=NULL, share_expires=NULL WHERE id=%s AND owner_id=%s",
                (note_id, owner),
            )

    def shared(self, token: str) -> Note:
        with connect() as conn:
            row = conn.execute(
                "SELECT id, title, group_name, cue, content, summary, tasks, version, updated_at FROM notes WHERE share_hash=%s AND share_expires>%s",
                (hashlib.sha256(token.encode()).hexdigest(), datetime.now(UTC)),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "共有リンクが無効または期限切れです")
            return decode(row)


def store() -> NoteStore:
    return PostgresStore()
