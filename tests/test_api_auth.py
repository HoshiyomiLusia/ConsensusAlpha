from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.main import app
from app.core.config import Settings


def test_health_remains_available_when_api_auth_is_required():
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        app_env="production",
        api_auth_token="secret-token",
    )
    try:
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_protected_routes_require_valid_bearer_token_in_production():
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        app_env="production",
        api_auth_token="secret-token",
    )
    try:
        with TestClient(app) as client:
            missing = client.get("/settings")
            assert missing.status_code == 401

            bad = client.get("/settings", headers={"Authorization": "Bearer wrong-token"})
            assert bad.status_code == 401

            good = client.get("/settings", headers={"Authorization": "Bearer secret-token"})
            assert good.status_code == 200
            assert good.json()["app_env"] == "production"
    finally:
        app.dependency_overrides.clear()


def test_auth_required_without_configured_token_fails_closed():
    app.dependency_overrides[get_app_settings] = lambda: Settings(api_auth_enabled=True)
    try:
        with TestClient(app) as client:
            response = client.get("/settings")
            assert response.status_code == 503
            assert "no token is configured" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
