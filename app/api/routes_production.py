from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_app_settings
from app.brokers.factory import build_broker_provider
from app.core.config import Settings

router = APIRouter(prefix="/production", tags=["production"])


class ReadinessCheck(BaseModel):
    name: str
    passed: bool
    severity: Literal["blocker", "warning"] = "blocker"
    summary: str
    details: dict = Field(default_factory=dict)


class ProductionReadinessResponse(BaseModel):
    ready: bool
    live_trading_ready: bool
    checks: list[ReadinessCheck]


@router.get("/readiness", response_model=ProductionReadinessResponse)
async def production_readiness(
    settings: Settings = Depends(get_app_settings),
) -> ProductionReadinessResponse:
    checks: list[ReadinessCheck] = []

    def add(
        name: str,
        passed: bool,
        summary: str,
        *,
        severity: Literal["blocker", "warning"] = "blocker",
        details: dict | None = None,
    ) -> None:
        checks.append(
            ReadinessCheck(
                name=name,
                passed=passed,
                severity=severity,
                summary=summary,
                details=details or {},
            )
        )

    add(
        "app_env_production",
        settings.app_env.lower() == "production",
        "真实资金上线时 APP_ENV 必须是 production。",
        details={"app_env": settings.app_env},
    )
    add(
        "api_auth_configured",
        settings.api_auth_required and bool(settings.api_auth_token),
        "必须开启 API 访问保护，并配置非空访问口令。",
        details={
            "api_auth_enabled": settings.api_auth_enabled,
            "api_auth_required": settings.api_auth_required,
            "has_api_auth_token": bool(settings.api_auth_token),
        },
    )
    add(
        "database_is_postgres",
        settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")),
        "生产环境必须使用 PostgreSQL，不能使用本地 SQLite 兜底库。",
        details={"database_url_kind": settings.database_url.split(":", 1)[0]},
    )
    add(
        "broker_is_webull",
        settings.broker_provider == "webull",
        "真实交易必须使用 Webull 数据源和交易通道。",
        details={"broker_provider": settings.broker_provider},
    )
    add(
        "webull_production_env",
        settings.webull_env == "production",
        "真实资金上线时 Webull 环境必须是 production。",
        details={"webull_env": settings.webull_env},
    )
    add(
        "webull_credentials",
        settings.has_webull_credentials and bool(settings.webull_account_id),
        "必须配置 Webull App Key、App Secret 和账户 ID。",
        details={
            "has_webull_credentials": settings.has_webull_credentials,
            "has_webull_account_id": bool(settings.webull_account_id),
        },
    )
    add(
        "live_trading_switches",
        settings.live_ordering_enabled,
        "TRADING_MODE 必须是 live，且 ENABLE_LIVE_TRADING 必须开启。",
        details={
            "trading_mode": settings.trading_mode,
            "enable_live_trading": settings.enable_live_trading,
        },
    )

    real_llm_count = sum(
        1
        for config in settings.effective_llm_agent_configs()
        if config.enabled and config.provider.lower() != "mock" and config.api_key and config.model
    )
    add(
        "real_llm_quorum",
        real_llm_count >= 3,
        "生产决策至少需要 3 个已启用的真实模型配置。",
        details={"real_llm_count": real_llm_count},
    )
    add(
        "risk_limits_sane",
        settings.max_position_pct <= 0.10
        and settings.max_single_trade_risk_pct <= 0.02
        and settings.max_daily_loss_pct <= 0.05
        and settings.live_preview_ttl_seconds <= 300,
        "生产上线前风控参数必须保持保守范围。",
        details={
            "max_position_pct": settings.max_position_pct,
            "max_single_trade_risk_pct": settings.max_single_trade_risk_pct,
            "max_daily_loss_pct": settings.max_daily_loss_pct,
            "live_preview_ttl_seconds": settings.live_preview_ttl_seconds,
        },
    )
    add(
        "daily_live_limits",
        settings.max_daily_live_order_count > 0 and settings.max_daily_live_notional > 0,
        "必须配置每日实盘订单数量上限和名义金额上限。",
        details={
            "max_daily_live_order_count": settings.max_daily_live_order_count,
            "max_daily_live_notional": str(settings.max_daily_live_notional),
        },
    )
    add(
        "regular_hours_only",
        settings.regular_trading_hours_only,
        "生产上线应限制只能在美股常规交易时段下实盘订单。",
        details={"regular_trading_hours_only": settings.regular_trading_hours_only},
    )
    add(
        "holiday_calendar_uat",
        False,
        "真实资金上线前必须用券商 UAT 验证节假日和提前收盘日行为。",
        severity="warning",
    )

    provider_ok = False
    provider_details: dict = {}
    try:
        provider_status = await build_broker_provider(settings).status()
        provider_ok = provider_status.healthy
        provider_details = provider_status.model_dump(mode="json")
    except Exception as exc:
        provider_details = {"error_type": type(exc).__name__, "message": str(exc)}
    add(
        "provider_connectivity",
        provider_ok,
        "当前配置的券商数据源必须可连接。",
        details=provider_details,
    )

    blocker_failures = [check for check in checks if check.severity == "blocker" and not check.passed]
    ready = not blocker_failures
    return ProductionReadinessResponse(
        ready=ready,
        live_trading_ready=ready and settings.live_ordering_enabled,
        checks=checks,
    )
