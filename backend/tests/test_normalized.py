import json
import os
import shutil
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from app.auth import authenticate
from app.db import PostgresSession, connect, database
from app.main import create_app
from app.migrate import migrate
from app.port import UpdateConflict
from fastapi.testclient import TestClient
from psycopg import sql

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("PostgreSQL is required")
    migrate()
    instance = create_app()
    instance.dependency_overrides[authenticate] = lambda: "alice"
    return TestClient(instance, raise_server_exceptions=False)


def payload(title="分割モデル"):
    return {
        "title": title,
        "group": "学習",
        "cue": "問い",
        "content": "本文",
        "summary": "要約",
        "tasks": [
            {"id": str(uuid4()), "text": "復習", "done": False, "due": "2026-09-20"},
            {"id": str(uuid4()), "text": "資料を読む", "done": True, "due": None},
        ],
    }


def test_正規化した記入欄とタスクと共有を所有者単位で取得する(client):
    data = payload()
    response = client.post("/api/notes", json=data)
    assert response.status_code == 201
    note = response.json()
    url = "/api/notes/" + note["id"]
    assert client.get(url).json() == note
    tasks = [t for t in client.get("/api/tasks").json() if t["note_id"] == note["id"]]
    assert len(tasks) == 2 and {t["done"] for t in tasks} == {False, True}
    assert tasks[0]["title"] == data["title"]
    with connect() as conn:
        assert conn.execute("SELECT id FROM users WHERE id='alice'").fetchone()
        assert (
            conn.execute("SELECT kind FROM note_sections WHERE note_id=%s", (note["id"],)).rowcount
            == 3
        )
        assert (
            conn.execute("SELECT id FROM note_tasks WHERE note_id=%s", (note["id"],)).rowcount == 2
        )
    client.app.dependency_overrides[authenticate] = lambda: "bob"
    assert client.get(url).status_code == 404
    assert not any(t["note_id"] == note["id"] for t in client.get("/api/tasks").json())
    assert client.post(url + "/share").status_code == 404
    client.app.dependency_overrides[authenticate] = lambda: "alice"
    token = client.post(url + "/share").json()["token"]
    assert client.get("/api/shared/" + token).json() == note
    assert client.delete(url).status_code == 204
    with connect() as conn:
        for table in ("note_sections", "note_tasks", "note_shares"):
            assert not conn.execute(
                sql.SQL("SELECT note_id FROM {} WHERE note_id=%s").format(sql.Identifier(table)),
                (note["id"],),
            ).fetchall()


def test_子テーブル書込の途中失敗で基本情報と全子データを巻き戻す(client, monkeypatch):
    original = payload()
    note = client.post("/api/notes", json=original).json()
    url = "/api/notes/" + note["id"]
    old_execute = PostgresSession.execute

    def fail(self, path, params):
        if (
            path.parent.parent.name == "update_note"
            and "insert_task" in path.name
            and params["position"] == 1
        ):
            raise RuntimeError("injected child failure")
        return old_execute(self, path, params)

    monkeypatch.setattr(PostgresSession, "execute", fail)
    changed = payload("失敗した題名") | {"version": note["version"]}
    assert client.put(url, json=changed).status_code == 500
    assert client.get(url).json() == note
    assert len([t for t in client.get("/api/tasks").json() if t["note_id"] == note["id"]]) == 2
    assert client.delete(url).status_code == 204


def test_新規保存の失敗で初回ユーザーも残さない(client, monkeypatch):
    owner = "rollback-" + str(uuid4())
    client.app.dependency_overrides[authenticate] = lambda: owner
    old_execute = PostgresSession.execute

    def fail(self, path, params):
        if "insert_section" in path.name:
            raise RuntimeError("injected section failure")
        return old_execute(self, path, params)

    monkeypatch.setattr(PostgresSession, "execute", fail)
    assert client.post("/api/notes", json=payload()).status_code == 500
    with connect() as conn:
        assert not conn.execute("SELECT id FROM users WHERE id=%s", (owner,)).fetchall()
        assert not conn.execute("SELECT id FROM notes WHERE owner_id=%s", (owner,)).fetchall()


def test_コミット時競合では成功を返さず全変更を巻き戻す(client):
    note = client.post("/api/notes", json=payload()).json()

    class ConflictAtCommit:
        calls = 0

        @contextmanager
        def transaction(self):
            self.calls += 1
            try:
                with connect() as conn:
                    yield PostgresSession(conn)
                    raise psycopg.errors.SerializationFailure("injected commit conflict")
            except psycopg.errors.SerializationFailure as exc:
                raise UpdateConflict from exc

    repo = ConflictAtCommit()
    client.app.dependency_overrides[database] = lambda: repo
    url = "/api/notes/" + note["id"]
    response = client.put(url, json=payload("競合した題名") | {"version": note["version"]})
    assert response.status_code == 409 and repo.calls == 1
    del client.app.dependency_overrides[database]
    assert client.get(url).json() == note
    client.delete(url)


def test_同じノート内で重複したタスクIDを入力時点で拒否する(client):
    data = payload()
    data["tasks"][1]["id"] = data["tasks"][0]["id"]
    assert client.post("/api/notes", json=data).status_code == 422


@pytest.fixture
def legacy(monkeypatch, tmp_path):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("PostgreSQL is required")
    import app.migrate as migration

    name = "migration_" + uuid4().hex
    with connect() as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))

    def scoped(*, admin=False):
        conn = connect(admin=admin)
        conn.autocommit = True
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(name)))
        return conn

    monkeypatch.setattr(migration, "connect", scoped)
    monkeypatch.setenv("MIGRATIONS_DIR", str(tmp_path))
    for path in sorted(Path("backend/migrations").glob("00[123]*.sql")):
        shutil.copy(path, tmp_path / path.name)
    migrate()
    data = payload("移行前のノート")
    identifier = uuid4()
    expires = datetime.now(UTC) + timedelta(days=7)
    with scoped() as conn:
        conn.execute(
            "INSERT INTO notes (id, owner_id, title, group_name, cue, content, summary, tasks, version, updated_at, share_hash, share_expires) VALUES (%s,'legacy-owner',%s,%s,%s,%s,%s,%s,7,%s,%s,%s)",
            (
                identifier,
                data["title"],
                data["group"],
                data["cue"],
                data["content"],
                data["summary"],
                json.dumps(data["tasks"]),
                datetime.now(UTC),
                "a" * 64,
                expires,
            ),
        )
    shutil.copytree("backend/migrations", tmp_path, dirs_exist_ok=True)
    yield scoped, identifier, data, expires
    with connect() as conn:
        conn.execute("RESET search_path")
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))


def test_旧データを失わず移行し再実行でも重複しない(legacy):
    scoped, identifier, data, expires = legacy
    migrate()
    migrate()
    with scoped() as conn:
        assert (
            conn.execute("SELECT version FROM notes WHERE id=%s", (identifier,)).fetchone()[
                "version"
            ]
            == 7
        )
        assert {
            r["kind"]: r["body"]
            for r in conn.execute(
                "SELECT kind, body FROM note_sections WHERE note_id=%s", (identifier,)
            ).fetchall()
        } == {k: data[k] for k in ("cue", "content", "summary")}
        tasks = conn.execute(
            "SELECT id, text, done, due FROM note_tasks WHERE note_id=%s ORDER BY position",
            (identifier,),
        ).fetchall()
        assert [str(t["id"]) for t in tasks] == [t["id"] for t in data["tasks"]]
        assert [t["done"] for t in tasks] == [False, True]
        assert str(tasks[0]["due"]) == "2026-09-20"
        assert (
            conn.execute(
                "SELECT expires_at FROM note_shares WHERE note_id=%s", (identifier,)
            ).fetchone()["expires_at"]
            == expires
        )
        assert not conn.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid='notes'::regclass AND attname='tasks' AND NOT attisdropped"
        ).fetchone()
        assert conn.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()["n"] == 7
        assert conn.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid='notes'::regclass AND conname='notes_owner_fk'"
        ).fetchone()


def test_移行で不正なタスクを検出したら旧カラムを残す(legacy):
    scoped, identifier, data, _ = legacy
    data["tasks"][1]["id"] = data["tasks"][0]["id"]
    with scoped() as conn:
        conn.execute(
            "UPDATE notes SET tasks=%s WHERE id=%s", (json.dumps(data["tasks"]), identifier)
        )
    with pytest.raises(ValueError, match="重複"):
        migrate()
    with scoped() as conn:
        assert conn.execute("SELECT tasks FROM notes WHERE id=%s", (identifier,)).fetchone()
        assert not conn.execute(
            "SELECT name FROM schema_migrations WHERE name='005_split_note_data'"
        ).fetchone()
        assert not conn.execute(
            "SELECT note_id FROM note_sections WHERE note_id=%s", (identifier,)
        ).fetchall()


def test_データ移行の途中停止後はコピー済みノートを照合して再開する(legacy):
    from uuid import UUID

    scoped, identifier, data, _ = legacy
    later = UUID(int=2**128 - 1)
    invalid = payload("後続ノート")
    invalid["tasks"][1]["id"] = invalid["tasks"][0]["id"]
    with scoped() as conn:
        conn.execute(
            "INSERT INTO notes (id, owner_id, title, group_name, cue, content, summary, tasks, version, updated_at) VALUES (%s,'legacy-owner','後続ノート','学習','問い','本文','要約',%s,1,%s)",
            (later, json.dumps(invalid["tasks"]), datetime.now(UTC)),
        )
    with pytest.raises(ValueError, match="重複"):
        migrate()
    with scoped() as conn:
        assert (
            conn.execute("SELECT kind FROM note_sections WHERE note_id=%s", (identifier,)).rowcount
            == 3
        )
        assert conn.execute("SELECT tasks FROM notes WHERE id=%s", (identifier,)).fetchone()
        conn.execute("UPDATE notes SET tasks=%s WHERE id=%s", (json.dumps(data["tasks"]), later))
    migrate()
    with scoped() as conn:
        assert (
            conn.execute("SELECT kind FROM note_sections WHERE note_id=%s", (identifier,)).rowcount
            == 3
        )
        assert (
            conn.execute("SELECT kind FROM note_sections WHERE note_id=%s", (later,)).rowcount == 3
        )
        assert (
            conn.execute("SELECT id FROM note_tasks WHERE note_id=%s", (identifier,)).rowcount == 2
        )
        assert conn.execute("SELECT id FROM note_tasks WHERE note_id=%s", (later,)).rowcount == 2
