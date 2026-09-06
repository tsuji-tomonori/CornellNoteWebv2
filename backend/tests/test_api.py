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


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_rejects_bad_password():
    assert (
        client.post("/api/auth/local", json={"username": "alice", "password": "wrong"}).status_code
        == 401
    )


def test_login_issues_signed_expiring_subject():
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


def test_private_routes_reject_missing_and_expired_tokens():
    assert client.get("/api/notes").status_code == 401
    token = jwt.encode(
        {"sub": "alice", "aud": "cornell-local", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings().local_secret,
        algorithm="HS256",
    )
    assert client.get("/api/notes", headers={"Authorization": "Bearer " + token}).status_code == 401
    assert client.get("/api/notes", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_lambda_refuses_local_auth(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "production")
    with pytest.raises(RuntimeError, match="forbidden"):
        Settings().validate()


def test_input_limits():
    with pytest.raises(ValueError):
        NoteInput(title="")
    with pytest.raises(ValueError):
        NoteInput(title="  ")
    with pytest.raises(ValueError):
        NoteInput(title="x", tasks=[{"id": str(uuid4()), "text": "", "done": False}])
    with pytest.raises(ValueError):
        NoteInput(title="x", owner_id="another-user")
