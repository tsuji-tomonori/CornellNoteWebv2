import json

from pydantic import BaseModel

from app.models import Note


def decode(row: BaseModel) -> Note:
    value = row.model_dump()
    value["group"] = value.pop("group_name")
    value["tasks"] = json.loads(value["tasks"])
    return Note.model_validate(value)
