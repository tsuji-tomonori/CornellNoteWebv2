from datetime import datetime

from app.models import Note
from app.note_mapping import assemble
from app.port import QuerySession

from .generated import queries


def select_note(
    token_hash: str, expires_at: datetime, session: QuerySession
) -> list[queries.SelectNoteRow]:
    return queries.select_note(
        session, queries.SelectNoteParams(token_hash=token_hash, expires_at=expires_at)
    )


def select_sections(
    token_hash: str, expires_at: datetime, session: QuerySession
) -> list[queries.SelectSectionsRow]:
    return queries.select_sections(
        session, queries.SelectSectionsParams(token_hash=token_hash, expires_at=expires_at)
    )


def select_tasks(
    token_hash: str, expires_at: datetime, session: QuerySession
) -> list[queries.SelectTasksRow]:
    return queries.select_tasks(
        session, queries.SelectTasksParams(token_hash=token_hash, expires_at=expires_at)
    )


def response(
    rows: list[queries.SelectNoteRow],
    sections: list[queries.SelectSectionsRow],
    tasks: list[queries.SelectTasksRow],
) -> Note:
    return assemble(rows[0], sections, tasks)


def digest(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()
