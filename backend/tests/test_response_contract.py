from contextlib import contextmanager
from uuid import uuid4

import pytest
from app.auth import authenticate
from app.db import database
from app.main import create_app
from app.port import UpdateConflict
from fastapi.testclient import TestClient


class Results:
    def __init__(self, rows):
        self.rows = rows

    def fetch_all(self, sql_path, params):
        return self.rows

    def execute(self, sql_path, params):
        return None


class StubDatabase:
    def __init__(self, *, rows=(), error=None):
        self.rows, self.error, self.calls = list(rows), error, 0

    @contextmanager
    def transaction(self):
        self.calls += 1
        if self.error:
            raise self.error
        yield Results(self.rows)


@pytest.fixture
def setup_client():
    instance = create_app()
    instance.dependency_overrides[authenticate] = lambda: "alice"

    def client_for(repo):
        instance.dependency_overrides[database] = lambda: repo
        return TestClient(instance, raise_server_exceptions=False, follow_redirects=False)

    return client_for


def test_空一覧は200でDB障害は本文を漏らさず500にする(setup_client):
    repo = StubDatabase()
    response = setup_client(repo).get("/api/notes")
    assert response.status_code == 200
    assert response.json() == []
    assert repo.calls == 1
    response = setup_client(StubDatabase(error=RuntimeError("private database error"))).get(
        "/api/notes"
    )
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert response.headers["content-type"].startswith("text/plain")
    assert "private" not in response.text


def test_ルート不一致と不正入力を区別してDBにアクセスしない(setup_client):
    repo = StubDatabase()
    client = setup_client(repo)
    response = client.get("/api/unknown-endpoint")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    response = client.patch("/api/notes")
    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
    assert response.headers["allow"]
    response = client.get("/api/notes/")
    assert response.status_code == 307
    assert response.headers["location"].endswith("/api/notes")
    for response in [
        client.get("/api/notes/not-a-uuid"),
        client.post("/api/notes", json={"title": ""}),
        client.post("/api/notes", content="{"),
    ]:
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
    assert repo.calls == 0


def test_存在しないノートと更新競合と本文なし応答を区別する(setup_client):
    identifier = str(uuid4())
    client = setup_client(StubDatabase())
    response = client.get("/api/notes/" + identifier)
    assert response.status_code == 404
    assert response.json() == {"detail": "ノートが見つかりません"}
    for path in ["/api/notes/" + identifier, "/api/notes/" + identifier + "/share"]:
        response = client.delete(path)
        assert response.status_code == 204
        assert response.content == b""
    response = setup_client(StubDatabase(error=UpdateConflict())).put(
        "/api/notes/" + identifier, json={"title": "変更", "version": 1}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "更新が競合しました。再読み込みしてください"}
