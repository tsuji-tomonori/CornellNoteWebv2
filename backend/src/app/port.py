from collections.abc import Mapping
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class UpdateConflict(Exception):
    pass


class QuerySession(Protocol):
    def fetch_all(
        self, sql_path: Path, params: Mapping[str, object]
    ) -> list[Mapping[str, object]]: ...

    def execute(self, sql_path: Path, params: Mapping[str, object]) -> None: ...


class Database(Protocol):
    def transaction(self) -> AbstractContextManager[QuerySession]: ...
