import hashlib
from datetime import UTC, datetime

from app.models import Note
from app.note_mapping import decode
from app.port import Database
from fastapi import HTTPException

from .generated import queries


def execute(token: str, repo: Database) -> Note:
    """期限内の共有ノートを閲覧用に返す。"""
    params = queries.SelectSharedNoteParams(
        share_hash=hashlib.sha256(token.encode()).hexdigest(), share_expires=datetime.now(UTC)
    )
    with repo.transaction() as session:
        rows = queries.select_shared_note(session, params)
    if not rows:
        raise HTTPException(404, "共有リンクが無効または期限切れです")
    return decode(rows[0])
