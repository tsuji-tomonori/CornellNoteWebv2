from app.models import TaskOverview
from app.port import QuerySession

from .generated import queries


def select(owner: str, session: QuerySession) -> list[TaskOverview]:
    rows = queries.select_tasks(session, queries.SelectTasksParams(owner_id=owner))
    return [TaskOverview.model_validate(row.model_dump()) for row in rows]
