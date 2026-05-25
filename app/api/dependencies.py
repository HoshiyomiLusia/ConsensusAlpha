import hashlib
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.agents.llm_provider import build_llm_provider
from app.brokers.factory import build_broker_provider
from app.core.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings() -> Settings:
    return get_settings()


def require_operator_auth(
    request: Request,
    settings: Settings = Depends(get_app_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if not settings.api_auth_required:
        request.state.operator_actor = "local"
        return
    if not settings.api_auth_token:
        raise HTTPException(status_code=503, detail="API authentication is required but no token is configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="API token is required")
    if not secrets.compare_digest(credentials.credentials, settings.api_auth_token):
        raise HTTPException(status_code=401, detail="API token is invalid")
    fingerprint = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()[:12]
    request.state.operator_actor = f"token:{fingerprint}"


def audit_actor(request: Request) -> str:
    return getattr(request.state, "operator_actor", "local")


def get_broker_provider(settings: Settings | None = None):
    return build_broker_provider(settings or get_settings())


def get_llm_provider(settings: Settings | None = None):
    return build_llm_provider(settings or get_settings())
