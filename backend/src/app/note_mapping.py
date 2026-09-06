from collections.abc import Sequence

from pydantic import BaseModel

from app.models import Note


def assemble(row: BaseModel, sections: Sequence[BaseModel], tasks: Sequence[BaseModel]) -> Note:
    value = row.model_dump()
    value["group"] = value.pop("group_name")
    value.update(
        {
            s.model_dump()["kind"]: s.model_dump()["body"]
            for s in sections
            if s.model_dump()["note_id"] == value["id"]
        }
    )
    value["tasks"] = [
        t.model_dump(exclude={"note_id"}) for t in tasks if t.model_dump()["note_id"] == value["id"]
    ]
    return Note.model_validate(value)


def assemble_many(
    rows: Sequence[BaseModel], sections: Sequence[BaseModel], tasks: Sequence[BaseModel]
) -> list[Note]:
    return [assemble(row, sections, tasks) for row in rows]
