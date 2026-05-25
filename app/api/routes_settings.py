import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import audit_actor, get_app_settings
from app.core.config import AgentLLMConfig, Settings, get_settings
from app.storage.database import get_db
from app.storage.repositories import create_audit_event

router = APIRouter(tags=["settings"])

ENV_FILE = Path(".env")


class SettingsUpdateRequest(BaseModel):
    app_env: str | None = None
    api_auth_enabled: bool | None = None
    api_auth_token: str | None = None
    broker_provider: Literal["mock", "webull"] | None = None
    trading_mode: Literal["paper", "live"] | None = None
    enable_live_trading: bool | None = None

    webull_env: Literal["test", "production"] | None = None
    webull_app_key: str | None = None
    webull_app_secret: str | None = None
    webull_region: str | None = None
    webull_account_id: str | None = None
    webull_trading_endpoint_test: str | None = None
    webull_market_data_endpoint_test: str | None = None
    webull_trading_endpoint_production: str | None = None
    webull_market_data_endpoint_production: str | None = None

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_agent_configs: list[AgentLLMConfig] | None = None
    mock_agent_action: Literal["BUY", "SELL", "HOLD", ""] | None = None

    max_position_pct: float | None = Field(default=None, ge=0)
    max_single_trade_risk_pct: float | None = Field(default=None, ge=0)
    max_daily_loss_pct: float | None = Field(default=None, ge=0)
    min_agent_confidence: float | None = Field(default=None, ge=0, le=1)
    trade_cooldown_seconds: int | None = Field(default=None, ge=0)
    max_order_price_deviation_pct: float | None = Field(default=None, ge=0)
    live_preview_ttl_seconds: int | None = Field(default=None, ge=1)
    max_daily_live_order_count: int | None = Field(default=None, ge=0)
    max_daily_live_notional: Decimal | None = Field(default=None, ge=0)
    regular_trading_hours_only: bool | None = None


@router.get("/settings")
def settings(settings: Settings = Depends(get_app_settings)) -> dict:
    return settings.redacted()


@router.patch("/settings")
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> dict:
    updates = _clean_updates(payload, settings)
    if not updates:
        return settings.redacted()

    prospective = settings.model_dump()
    prospective.update({key.lower(): value for key, value in updates.items()})
    try:
        candidate = Settings(**prospective)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    if candidate.api_auth_required and not candidate.api_auth_token:
        raise HTTPException(
            status_code=422,
            detail="api_auth_token is required when API authentication or production app_env is enabled",
        )

    _write_env_file(updates)
    get_settings.cache_clear()
    next_settings = get_settings()
    create_audit_event(
        db,
        actor=audit_actor(request),
        action="settings.update",
        entity_type="settings",
        entity_id="runtime",
        summary=f"更新了 {len(updates)} 项运行配置",
        payload={"changed_keys": sorted(updates.keys())},
    )
    db.commit()
    return next_settings.redacted()


def _clean_updates(payload: SettingsUpdateRequest, settings: Settings) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    updates: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if key == "llm_agent_configs":
            updates[key.upper()] = _merge_agent_config_secrets(value, settings)
            continue
        if isinstance(value, str):
            if "\n" in value or "\r" in value:
                raise HTTPException(status_code=400, detail=f"{key} cannot contain newlines")
            if value == "" and key in {"api_auth_token", "webull_app_key", "webull_app_secret", "llm_api_key"}:
                continue
        updates[key.upper()] = value
    return updates


def _merge_agent_config_secrets(configs: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    existing_by_role = {config.role: config for config in settings.effective_llm_agent_configs()}
    cleaned: list[dict[str, Any]] = []
    seen_roles: set[str] = set()

    for item in configs:
        config = AgentLLMConfig(**item)
        if config.role in seen_roles:
            raise HTTPException(status_code=400, detail=f"duplicate LLM agent role: {config.role}")
        seen_roles.add(config.role)

        if not config.api_key:
            existing = existing_by_role.get(config.role)
            if existing:
                config.api_key = existing.api_key

        if config.provider.lower() != "mock":
            if not config.model:
                raise HTTPException(status_code=422, detail=f"{config.role} model is required")
            if not config.base_url:
                raise HTTPException(status_code=422, detail=f"{config.role} base_url is required")
            if not config.api_key:
                raise HTTPException(status_code=422, detail=f"{config.role} api_key is required")

        cleaned.append(config.model_dump())

    return cleaned


def _write_env_file(updates: dict[str, Any]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    remaining = dict(updates)
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue

        key, _ = line.split("=", 1)
        env_key = key.strip()
        if env_key in remaining:
            next_lines.append(f"{env_key}={_serialize_env_value(remaining.pop(env_key))}")
        else:
            next_lines.append(line)

    if remaining and next_lines and next_lines[-1] != "":
        next_lines.append("")
    for key, value in remaining.items():
        next_lines.append(f"{key}={_serialize_env_value(value)}")

    ENV_FILE.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


def _serialize_env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    text = str(value)
    if text == "":
        return ""
    if any(char.isspace() for char in text) or "#" in text:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text
