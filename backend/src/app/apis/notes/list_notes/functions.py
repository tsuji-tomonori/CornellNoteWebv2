from app.models import Note
from app.note_mapping import assemble_many
from app.port import QuerySession

from .generated import queries


def select_notes(owner: str, session: QuerySession) -> list[queries.SelectNotesRow]:
    return queries.select_notes(session, queries.SelectNotesParams(owner_id=owner))


def select_sections(owner: str, session: QuerySession) -> list[queries.SelectSectionsRow]:
    return queries.select_sections(session, queries.SelectSectionsParams(owner_id=owner))


def select_tasks(owner: str, session: QuerySession) -> list[queries.SelectTasksRow]:
    return queries.select_tasks(session, queries.SelectTasksParams(owner_id=owner))


def response(
    rows: list[queries.SelectNotesRow],
    sections: list[queries.SelectSectionsRow],
    tasks: list[queries.SelectTasksRow],
) -> list[Note]:
    return assemble_many(rows, sections, tasks)
