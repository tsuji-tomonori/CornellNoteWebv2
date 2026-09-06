from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from app.auth import settings
from app.config import Settings
from app.main import app
from app.models import NoteInput
from fastapi.testclient import TestClient

client = TestClient(app)


def test_ヘルスチェックが正常応答する():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_誤ったパスワードを拒否する():
    assert (
        client.post("/api/auth/local", json={"username": "alice", "password": "wrong"}).status_code
        == 401
    )


def test_署名と有効期限と本人情報を持つJWTを発行する():
    response = client.post(
        "/api/auth/local", json={"username": "alice", "password": "cornell-local"}
    )
    claims = jwt.decode(
        response.json()["access_token"],
        settings().local_secret,
        algorithms=["HS256"],
        audience="cornell-local",
    )
    assert claims["sub"] == "alice"
    assert claims["exp"] > datetime.now(UTC).timestamp()


def test_未認証と期限切れのノート操作を拒否する():
    assert client.get("/api/notes").status_code == 401
    token = jwt.encode(
        {"sub": "alice", "aud": "cornell-local", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings().local_secret,
        algorithm="HS256",
    )
    assert client.get("/api/notes", headers={"Authorization": "Bearer " + token}).status_code == 401
    assert client.get("/api/notes", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_Lambdaではローカル認証を起動しない(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "production")
    with pytest.raises(RuntimeError, match="forbidden"):
        Settings().validate()


def test_入力長と余分な項目を検証する():
    with pytest.raises(ValueError):
        NoteInput(title="")
    with pytest.raises(ValueError):
        NoteInput(title="  ")
    with pytest.raises(ValueError):
        NoteInput(title="x", tasks=[{"id": str(uuid4()), "text": "", "done": False}])
    with pytest.raises(ValueError):
        NoteInput(title="x", owner_id="another-user")
