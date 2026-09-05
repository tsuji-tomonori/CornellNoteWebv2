import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    auth_mode: str = field(default_factory=lambda: os.getenv("AUTH_MODE", "cognito"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    dsql_host: str = field(default_factory=lambda: os.getenv("DSQL_HOST", ""))
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-northeast-1"))
    issuer: str = field(default_factory=lambda: os.getenv("COGNITO_ISSUER", ""))
    client_id: str = field(default_factory=lambda: os.getenv("COGNITO_CLIENT_ID", ""))
    local_secret: str = field(default_factory=lambda: os.getenv("LOCAL_AUTH_SECRET", ""))
    local_password: str = field(default_factory=lambda: os.getenv("LOCAL_PASSWORD", ""))

    def validate(self) -> None:
        if self.auth_mode not in {"local", "cognito"}:
            raise RuntimeError("Unknown AUTH_MODE")
        if self.auth_mode == "local":
            if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
                raise RuntimeError("Local authentication is forbidden in Lambda")
            if len(self.local_secret) < 32 or not self.local_password:
                raise RuntimeError("Explicit local credentials are required")
