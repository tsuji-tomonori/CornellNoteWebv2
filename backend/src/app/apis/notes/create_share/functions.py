from datetime import UTC, datetime
from uuid import UUID

from app.models import Share
from app.port import QuerySession

from .generated import queries


def find(note_id: UUID, owner: str, session: QuerySession) -> list[queries.SelectOwnedNoteRow]:
    return queries.select_owned_note(
        session, queries.SelectOwnedNoteParams(id=note_id, owner_id=owner)
    )


def remove(note_id: UUID, session: QuerySession) -> None:
    queries.delete_share(session, queries.DeleteShareParams(note_id=note_id))


def issue() -> Share:
    import secrets
    from datetime import timedelta

    return Share(token=secrets.token_urlsafe(32), expires_at=datetime.now(UTC) + timedelta(days=7))


def save(note_id: UUID, share: Share, owner: str, session: QuerySession) -> Share:
    import hashlib

    queries.insert_share(
        session,
        queries.InsertShareParams(
            note_id=note_id,
            token_hash=hashlib.sha256(share.token.encode()).hexdigest(),
            expires_at=share.expires_at,
            created_by=owner,
        ),
    )
    return share
