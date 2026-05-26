from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_ROLES = [
    "market_analyst",
    "risk_manager",
    "contrarian_critic",
    "execution_specialist",
    "chairperson",
]

US_TRADING_ENDPOINT_TEST = "us-openapi-alb.uat.webullbroker.com"
US_MARKET_DATA_ENDPOINT_TEST = "us-broker-api.uat.webullbroker.com"
US_TRADING_ENDPOINT_PRODUCTION = "api.webull.com"
US_MARKET_DATA_ENDPOINT_PRODUCTION = "broker-api.webull.com"

JP_TRADING_ENDPOINT_TEST = "jp-openapi-alb.uat.webullbroker.com"
JP_MARKET_DATA_ENDPOINT_TEST = "jp-openapi-alb.uat.webullbroker.com"
JP_TRADING_ENDPOINT_PRODUCTION = "api.webull.co.jp"
JP_MARKET_DATA_ENDPOINT_PRODUCTION = "api.webull.co.jp"

AgentRole = Literal[
    "market_analyst",
    "risk_manager",
    "contrarian_critic",
    "execution_specialist",
    "chairperson",
]


class AgentLLMConfig(BaseModel):
    role: AgentRole
    provider: str = "mock"
    model: str = ""
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    enabled: bool = True

    @field_validator("provider", "model", "base_url", "api_key")
    @classmethod
    def no_newlines(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("cannot contain newlines")
        return value.strip()

    def redacted(self) -> dict:
        return {
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "enabled": self.enabled,
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./consensus_alpha.db"
    api_auth_enabled: bool = False
    api_auth_token: str = ""

    broker_provider: Literal["mock", "webull"] = "mock"
    trading_mode: Literal["paper", "live"] = "paper"
    enable_live_trading: bool = False

    webull_env: Literal["test", "production"] = "test"
    webull_app_key: str = ""
    webull_app_secret: str = ""
    webull_region: str = "us"
    webull_account_id: str = ""
    webull_trading_endpoint_test: str = US_TRADING_ENDPOINT_TEST
    webull_market_data_endpoint_test: str = US_MARKET_DATA_ENDPOINT_TEST
    webull_trading_endpoint_production: str = US_TRADING_ENDPOINT_PRODUCTION
    webull_market_data_endpoint_production: str = US_MARKET_DATA_ENDPOINT_PRODUCTION

    llm_provider: str = "mock"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_agent_configs: list[AgentLLMConfig] = Field(default_factory=list)
    mock_agent_action: Literal["BUY", "SELL", "HOLD", ""] = ""

    max_position_pct: float = Field(default=0.05, ge=0)
    max_single_trade_risk_pct: float = Field(default=0.01, ge=0)
    max_daily_loss_pct: float = Field(default=0.02, ge=0)
    min_agent_confidence: float = Field(default=0.65, ge=0, le=1)
    trade_cooldown_seconds: int = Field(default=300, ge=0)
    max_order_price_deviation_pct: float = Field(default=0.05, ge=0)
    live_preview_ttl_seconds: int = Field(default=300, ge=1)
    max_daily_live_order_count: int = Field(default=5, ge=0)
    max_daily_live_notional: Decimal = Field(default=Decimal("5000"), ge=0)
    regular_trading_hours_only: bool = True

    @computed_field
    @property
    def webull_trading_endpoint(self) -> str:
        if self.webull_env == "production":
            return self._regional_endpoint(
                self.webull_trading_endpoint_production,
                US_TRADING_ENDPOINT_PRODUCTION,
                {"jp": JP_TRADING_ENDPOINT_PRODUCTION},
            )
        return self._regional_endpoint(
            self.webull_trading_endpoint_test,
            US_TRADING_ENDPOINT_TEST,
            {"jp": JP_TRADING_ENDPOINT_TEST},
        )

    @computed_field
    @property
    def webull_market_data_endpoint(self) -> str:
        if self.webull_env == "production":
            return self._regional_endpoint(
                self.webull_market_data_endpoint_production,
                US_MARKET_DATA_ENDPOINT_PRODUCTION,
                {"jp": JP_MARKET_DATA_ENDPOINT_PRODUCTION},
            )
        return self._regional_endpoint(
            self.webull_market_data_endpoint_test,
            US_MARKET_DATA_ENDPOINT_TEST,
            {"jp": JP_MARKET_DATA_ENDPOINT_TEST},
        )

    def _regional_endpoint(self, configured: str, default_us: str, regional_defaults: dict[str, str]) -> str:
        region = self.webull_region.strip().lower()
        if configured == default_us and region in regional_defaults:
            return regional_defaults[region]
        return configured

    @property
    def has_webull_credentials(self) -> bool:
        return bool(self.webull_app_key and self.webull_app_secret)

    @property
    def live_ordering_enabled(self) -> bool:
        return self.enable_live_trading and self.trading_mode == "live"

    @property
    def api_auth_required(self) -> bool:
        return self.api_auth_enabled or self.app_env.lower() == "production"

    def effective_llm_agent_configs(self) -> list[AgentLLMConfig]:
        configured = {config.role: config for config in self.llm_agent_configs}
        if configured:
            return [
                configured.get(role)
                or AgentLLMConfig(
                    role=role,  # type: ignore[arg-type]
                    provider=self.llm_provider,
                    model=self.llm_model,
                    base_url="" if self.llm_provider.lower() == "mock" else self.llm_base_url,
                    api_key=self.llm_api_key,
                )
                for role in AGENT_ROLES
            ]

        return [
            AgentLLMConfig(
                role=role,  # type: ignore[arg-type]
                provider=self.llm_provider,
                model=self.llm_model,
                base_url="" if self.llm_provider.lower() == "mock" else self.llm_base_url,
                api_key=self.llm_api_key,
            )
            for role in AGENT_ROLES
        ]

    def redacted(self) -> dict:
        return {
            "app_env": self.app_env,
            "api_auth_enabled": self.api_auth_enabled,
            "has_api_auth_token": bool(self.api_auth_token),
            "broker_provider": self.broker_provider,
            "trading_mode": self.trading_mode,
            "enable_live_trading": self.enable_live_trading,
            "webull_env": self.webull_env,
            "webull_region": self.webull_region,
            "webull_account_id": self._mask(self.webull_account_id),
            "webull_trading_endpoint": self.webull_trading_endpoint,
            "webull_market_data_endpoint": self.webull_market_data_endpoint,
            "webull_trading_endpoint_test": self.webull_trading_endpoint_test,
            "webull_market_data_endpoint_test": self.webull_market_data_endpoint_test,
            "webull_trading_endpoint_production": self.webull_trading_endpoint_production,
            "webull_market_data_endpoint_production": self.webull_market_data_endpoint_production,
            "has_webull_app_key": bool(self.webull_app_key),
            "has_webull_app_secret": bool(self.webull_app_secret),
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "has_llm_api_key": bool(self.llm_api_key),
            "llm_agent_configs": [config.redacted() for config in self.effective_llm_agent_configs()],
            "mock_agent_action": self.mock_agent_action,
            "max_position_pct": self.max_position_pct,
            "max_single_trade_risk_pct": self.max_single_trade_risk_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "min_agent_confidence": self.min_agent_confidence,
            "trade_cooldown_seconds": self.trade_cooldown_seconds,
            "max_order_price_deviation_pct": self.max_order_price_deviation_pct,
            "live_preview_ttl_seconds": self.live_preview_ttl_seconds,
            "max_daily_live_order_count": self.max_daily_live_order_count,
            "max_daily_live_notional": str(self.max_daily_live_notional),
            "regular_trading_hours_only": self.regular_trading_hours_only,
        }

    @staticmethod
    def _mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
