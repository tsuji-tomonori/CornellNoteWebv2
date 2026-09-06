import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.db import connect
from app.main import app
from app.migrate import migrate
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("PostgreSQL is required; CI runs this with Compose database")
    migrate()
    return TestClient(app)


def headers(client, user="alice"):
    token = client.post(
        "/api/auth/local", json={"username": user, "password": "cornell-local"}
    ).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def test_ノートの作成更新削除と所有者分離を確認する(client):
    alice, bob = headers(client), headers(client, "bob")
    created = client.post(
        "/api/notes", headers=alice, json={"title": "講義 " + str(uuid4()), "group": "情報工学"}
    )
    assert created.status_code == 201
    note = created.json()
    url = "/api/notes/" + note["id"]
    assert client.get(url, headers=bob).status_code == 404
    assert not any(n["id"] == note["id"] for n in client.get("/api/notes", headers=bob).json())
    update = {
        k: note[k] for k in ["title", "group", "cue", "content", "summary", "tasks", "version"]
    }
    update["content"] = "自分の言葉で記録"
    update["tasks"] = [{"id": str(uuid4()), "text": "復習", "done": True, "due": "2026-09-15"}]
    assert client.put(url, headers=bob, json=update).status_code == 404
    assert client.put(url, headers=alice, json=update).status_code == 200
    assert client.put(url, headers=alice, json=update).status_code == 409
    assert client.get(url, headers=alice).json()["tasks"][0]["done"] is True
    with connect() as conn:
        assert (
            conn.execute(
                "SELECT body FROM note_sections WHERE note_id=%s AND kind='content'", (note["id"],)
            ).fetchone()["body"]
            == update["content"]
        )
    client.delete(url, headers=bob)
    assert client.get(url, headers=alice).status_code == 200
    assert client.delete(url, headers=alice).status_code == 204
    assert client.get(url, headers=alice).status_code == 404


def test_共有の期限と再発行と解除を確認する(client):
    alice, bob = headers(client), headers(client, "bob")
    note = client.post("/api/notes", headers=alice, json={"title": "共有の学習"}).json()
    url = "/api/notes/" + note["id"]
    assert client.post(url + "/share", headers=bob).status_code == 404
    issued = client.post(url + "/share", headers=alice)
    assert issued.status_code == 200
    first = issued.json()["token"]
    assert client.get("/api/shared/" + first).status_code == 200
    second = client.post(url + "/share", headers=alice).json()["token"]
    assert client.get("/api/shared/" + first).status_code == 404
    assert client.get("/api/shared/" + second).status_code == 200
    with connect() as conn:
        row = conn.execute(
            "SELECT token_hash FROM note_shares WHERE note_id=%s", (note["id"],)
        ).fetchone()
        assert row["token_hash"] != second
        conn.execute(
            "UPDATE note_shares SET expires_at=%s WHERE note_id=%s",
            (datetime.now(UTC) - timedelta(seconds=1), note["id"]),
        )
    assert client.get("/api/shared/" + second).status_code == 404
    third = client.post(url + "/share", headers=alice).json()["token"]
    assert client.delete(url + "/share", headers=alice).status_code == 204
    assert client.get("/api/shared/" + third).status_code == 404
    client.delete(url, headers=alice)


def test_再マイグレーションでデータを保ち日本語カラム説明を保持する(client):
    migrate()
    migrate()
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()["n"] == 7
        rows = conn.execute(
            "SELECT col_description('notes'::regclass, ordinal_position) AS description FROM information_schema.columns WHERE table_name='notes'"
        ).fetchall()
        assert len(rows) == 6
        assert all(row["description"] for row in rows)


def test_引用符を含む入力をSQL構文ではなくデータとして保存する(client):
    alice = headers(client)
    title = "講義'; DROP TABLE notes; --"
    note = client.post("/api/notes", headers=alice, json={"title": title}).json()
    url = "/api/notes/" + note["id"]
    assert client.get(url, headers=alice).json()["title"] == title
    with connect() as conn:
        assert (
            conn.execute("SELECT title FROM notes WHERE id=%s", (note["id"],)).fetchone()["title"]
            == title
        )
    assert client.delete(url, headers=alice).status_code == 204
