from uuid import UUID

from app.models import Note
from app.note_mapping import assemble
from app.port import QuerySession

from .generated import queries


def select_note(note_id: UUID, owner: str, session: QuerySession) -> list[queries.SelectNoteRow]:
    return queries.select_note(session, queries.SelectNoteParams(id=note_id, owner_id=owner))


def select_sections(
    note_id: UUID, owner: str, session: QuerySession
) -> list[queries.SelectSectionsRow]:
    return queries.select_sections(
        session, queries.SelectSectionsParams(id=note_id, owner_id=owner)
    )


def select_tasks(note_id: UUID, owner: str, session: QuerySession) -> list[queries.SelectTasksRow]:
    return queries.select_tasks(session, queries.SelectTasksParams(id=note_id, owner_id=owner))


def response(
    rows: list[queries.SelectNoteRow],
    sections: list[queries.SelectSectionsRow],
    tasks: list[queries.SelectTasksRow],
) -> Note:
    return assemble(rows[0], sections, tasks)
