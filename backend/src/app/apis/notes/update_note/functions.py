from datetime import UTC, datetime
from uuid import UUID

from app.models import Note, NoteInput, NoteUpdate
from app.port import QuerySession

from .generated import queries


def find(note_id: UUID, owner: str, session: QuerySession) -> list[queries.SelectOwnedNoteRow]:
    return queries.select_owned_note(
        session, queries.SelectOwnedNoteParams(id=note_id, owner_id=owner)
    )


def update(
    note_id: UUID, data: NoteUpdate, owner: str, session: QuerySession
) -> list[queries.UpdateNoteRow]:
    return queries.update_note(
        session,
        queries.UpdateNoteParams(
            id=note_id,
            owner_id=owner,
            title=data.title,
            group_name=data.group,
            version=data.version,
            updated_at=datetime.now(UTC),
        ),
    )


def clear_children(note_id: UUID, session: QuerySession) -> None:
    queries.delete_sections(session, queries.DeleteSectionsParams(note_id=note_id))
    queries.delete_tasks(session, queries.DeleteTasksParams(note_id=note_id))


def response(row: queries.UpdateNoteRow, data: NoteUpdate) -> Note:
    return Note(
        **data.model_dump(exclude={"version"}),
        id=row.id,
        version=row.version,
        updated_at=row.updated_at,
    )


def save_sections(note_id: UUID, data: NoteInput, session: QuerySession) -> None:
    now = datetime.now(UTC)
    for kind in ("cue", "content", "summary"):
        queries.insert_section(
            session,
            queries.InsertSectionParams(
                note_id=note_id, kind=kind, body=getattr(data, kind), updated_at=now
            ),
        )


def save_tasks(note_id: UUID, data: NoteInput, session: QuerySession) -> None:
    for position, task in enumerate(data.tasks):
        queries.insert_task(
            session,
            queries.InsertTaskParams(
                note_id=note_id,
                id=task.id,
                text=task.text,
                done=task.done,
                due=task.due,
                position=position,
            ),
        )
