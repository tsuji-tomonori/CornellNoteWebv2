import json

from app.observability import ObservedRoute
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient


def test_成功と入力拒否と障害のログを出して秘密情報は記録しない(caplog):
    app = FastAPI()
    router = APIRouter(route_class=ObservedRoute)

    @router.get("/probe/{value}", operation_id="probe")
    def probe(value: int):
        if value == 404:
            raise HTTPException(404, "存在しない")
        if value == 500:
            raise RuntimeError("secret database text")
        return {"value": value}

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    for path, status in [("1", 200), ("bad", 422), ("404", 404), ("500", 500)]:
        response = client.get("/probe/" + path, headers={"Authorization": "Bearer secret-token"})
        assert response.status_code == status
    records = [json.loads(r.message) for r in caplog.records if r.name == "cornell.api"]
    assert [r["message_id"] for r in records] == [
        "probe.completed",
        "probe.rejected",
        "probe.rejected",
        "probe.failed",
    ]
    assert [r["status"] for r in records] == [200, 422, 404, 500]
    assert records[-1]["exception_type"] == "RuntimeError"
    assert "secret" not in json.dumps(records)
    assert response.text == "Internal Server Error"
