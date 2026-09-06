from functools import lru_cache
from typing import Protocol, cast

import boto3

from app.auth import settings


class DsqlClient(Protocol):
    def generate_db_connect_auth_token(self, *, Hostname: str) -> str: ...
    def generate_db_connect_admin_auth_token(self, *, Hostname: str) -> str: ...


@lru_cache
def client() -> DsqlClient:
    return cast(DsqlClient, boto3.client("dsql", region_name=settings().region))  # pyright: ignore[reportUnknownMemberType]


def auth_token(admin: bool) -> str:
    if admin:
        return client().generate_db_connect_admin_auth_token(Hostname=settings().dsql_host)
    return client().generate_db_connect_auth_token(Hostname=settings().dsql_host)
