from uuid import UUID

from app.port import QuerySession

from .generated import queries


def find(note_id: UUID, owner: str, session: QuerySession) -> list[queries.SelectOwnedNoteRow]:
    return queries.select_owned_note(
        session, queries.SelectOwnedNoteParams(id=note_id, owner_id=owner)
    )


def remove(note_id: UUID, session: QuerySession) -> None:
    queries.delete_share(session, queries.DeleteShareParams(note_id=note_id))
