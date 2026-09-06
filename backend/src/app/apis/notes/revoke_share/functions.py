from uuid import UUID

from app.port import Database

from .generated import queries


def execute(note_id: UUID, owner: str, repo: Database) -> None:
    """本人のノートの共有リンクを失効させる。"""
    with repo.transaction() as session:
        queries.revoke_share(session, queries.RevokeShareParams(id=note_id, owner_id=owner))
