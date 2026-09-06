from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.models import Note, NoteInput
from app.port import QuerySession

from .generated import queries


def ensure_user(owner: str, session: QuerySession) -> None:
    queries.insert_user(session, queries.InsertUserParams(id=owner, created_at=datetime.now(UTC)))


def create(data: NoteInput, owner: str, session: QuerySession) -> queries.InsertNoteRow:
    return queries.insert_note(
        session,
        queries.InsertNoteParams(
            id=uuid4(),
            owner_id=owner,
            title=data.title,
            group_name=data.group,
            updated_at=datetime.now(UTC),
        ),
    )[0]


def response(row: queries.InsertNoteRow, data: NoteInput) -> Note:
    return Note(**data.model_dump(), id=row.id, version=row.version, updated_at=row.updated_at)


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
