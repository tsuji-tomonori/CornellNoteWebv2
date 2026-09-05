import hmac
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings
from app.models import Login, Token

security = HTTPBearer(auto_error=False)


@lru_cache
def settings() -> Settings:
    value = Settings()
    value.validate()
    return value


@lru_cache
def jwks(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(issuer + "/.well-known/jwks.json")


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    if credentials is None:
        raise HTTPException(401, "ログインが必要です")
    cfg = settings()
    try:
        if cfg.auth_mode == "local":
            claims = jwt.decode(
                credentials.credentials,
                cfg.local_secret,
                algorithms=["HS256"],
                audience="cornell-local",
                options={"require": ["exp", "sub", "aud"]},
            )
        else:
            key = jwks(cfg.issuer).get_signing_key_from_jwt(credentials.credentials).key
            claims = jwt.decode(
                credentials.credentials,
                key,
                algorithms=["RS256"],
                issuer=cfg.issuer,
                options={
                    "verify_aud": False,
                    "require": ["exp", "sub", "iss", "token_use", "client_id"],
                },
            )
            if claims["token_use"] != "access" or claims["client_id"] != cfg.client_id:  # noqa: S105 -- OAuth token kind
                raise HTTPException(401, "認証情報が無効です")
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise HTTPException(401, "認証情報が無効です")
        return subject
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "認証情報が無効または期限切れです") from exc


def local_login(data: Login) -> Token:
    cfg = settings()
    if cfg.auth_mode != "local":
        raise HTTPException(404, "Not found")
    if not hmac.compare_digest(data.password, cfg.local_password):
        raise HTTPException(401, "ユーザー名またはパスワードが違います")
    token = jwt.encode(
        {
            "sub": data.username,
            "aud": "cornell-local",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        cfg.local_secret,
        algorithm="HS256",
    )
    return Token(access_token=token)
