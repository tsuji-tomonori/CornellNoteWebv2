import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

logger = logging.getLogger("cornell.api")
logger.setLevel(logging.INFO)


@dataclass(frozen=True)
class LogEvent:
    key: str
    minimum: int
    maximum: int
    level: int
    message: str


EVENTS = (
    LogEvent("completed", 200, 399, logging.INFO, "APIの処理が完了しました"),
    LogEvent(
        "rejected", 400, 499, logging.WARNING, "認証・入力・対象状態によりリクエストを拒否しました"
    ),
    LogEvent("failed", 500, 599, logging.ERROR, "APIの処理中に障害が発生しました"),
)


def emit(operation: str, status: int, exception: Exception | None = None) -> None:
    event = next(item for item in EVENTS if item.minimum <= status <= item.maximum)
    logger.log(
        event.level,
        json.dumps(
            {
                "message_id": f"{operation}.{event.key}",
                "message": event.message,
                "operation": operation,
                "status": status,
                "exception_type": type(exception).__name__ if exception else None,
            },
            ensure_ascii=False,
        ),
    )


class ObservedRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        original = super().get_route_handler()
        operation = self.operation_id or self.name

        async def observed(request: Request) -> Response:
            try:
                response = await original(request)
            except HTTPException as exc:
                emit(operation, exc.status_code, exc)
                raise
            except RequestValidationError as exc:
                emit(operation, 422, exc)
                raise
            except Exception as exc:
                emit(operation, 500, exc)
                raise
            emit(operation, response.status_code)
            return response

        return observed
