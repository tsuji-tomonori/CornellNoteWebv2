import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models import Share
from app.port import Database
from fastapi import HTTPException

from .generated import queries


def execute(note_id: UUID, owner: str, repo: Database) -> Share:
    """生トークンを保存せず、7日間の閲覧リンクを発行する。"""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=7)
    params = queries.UpdateShareParams(
        id=note_id,
        owner_id=owner,
        share_hash=hashlib.sha256(token.encode()).hexdigest(),
        share_expires=expires,
    )
    with repo.transaction() as session:
        rows = queries.update_share(session, params)
    if not rows:
        raise HTTPException(404, "ノートが見つかりません")
    return Share(token=token, expires_at=expires)
