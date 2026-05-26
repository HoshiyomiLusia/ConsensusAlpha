from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_app_settings
from app.brokers.factory import build_broker_provider
from app.brokers.webull_provider import WebullProvider
from app.core.config import Settings

router = APIRouter(tags=["provider"])


@router.get("/provider/status")
async def provider_status(settings: Settings = Depends(get_app_settings)) -> dict:
    provider = build_broker_provider(settings)
    status = await provider.status()
    return status.model_dump(mode="json")


class WebullAccountLookupRequest(BaseModel):
    webull_env: str = "test"
    webull_region: str = "us"
    webull_app_key: str = ""
    webull_app_secret: str = ""
    webull_trading_endpoint_test: str | None = None
    webull_trading_endpoint_production: str | None = None


@router.post("/provider/webull/accounts")
async def webull_accounts(
    payload: WebullAccountLookupRequest,
    current_settings: Settings = Depends(get_app_settings),
) -> dict:
    env = payload.webull_env if payload.webull_env in {"test", "production"} else "test"
    app_key = payload.webull_app_key.strip() or current_settings.webull_app_key
    app_secret = payload.webull_app_secret.strip() or current_settings.webull_app_secret
    if not app_key or not app_secret:
        raise HTTPException(status_code=422, detail="Webull App Key and App Secret are required")
    settings = Settings(
        broker_provider="webull",
        webull_env=env,  # type: ignore[arg-type]
        webull_region=payload.webull_region.strip() or "us",
        webull_app_key=app_key,
        webull_app_secret=app_secret,
        webull_trading_endpoint_test=payload.webull_trading_endpoint_test
        or current_settings.webull_trading_endpoint_test,
        webull_trading_endpoint_production=payload.webull_trading_endpoint_production
        or current_settings.webull_trading_endpoint_production,
    )
    try:
        accounts = await WebullProvider(settings).list_accounts()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "environment": settings.webull_env,
        "region": settings.webull_region,
        "accounts": accounts,
    }
