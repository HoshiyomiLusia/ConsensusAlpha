import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.agents.llm_provider import build_llm_provider
from app.core.config import AGENT_ROLES, AgentLLMConfig, Settings
from app.market_data.models import MarketContext, MarketSnapshot


def test_settings_redacts_per_agent_llm_secrets():
    settings = Settings(
        llm_agent_configs=[
            AgentLLMConfig(
                role="market_analyst",
                provider="openai",
                model="gpt-4.1",
                base_url="https://api.openai.com/v1",
                api_key="secret-key",
            )
        ]
    )

    redacted = settings.redacted()["llm_agent_configs"]
    market_config = next(config for config in redacted if config["role"] == "market_analyst")

    assert len(redacted) == len(AGENT_ROLES)
    assert market_config["has_api_key"] is True
    assert "api_key" not in market_config


def test_multi_agent_mock_provider_routes_by_role():
    settings = Settings(
        mock_agent_action="SELL",
        llm_agent_configs=[
            AgentLLMConfig(role=role, provider="mock")  # type: ignore[arg-type]
            for role in AGENT_ROLES
        ],
    )
    provider = build_llm_provider(settings)
    snapshot = MarketSnapshot(
        symbol="AAPL",
        asset_type="equity",
        price=Decimal("100"),
        timestamp=datetime.now(UTC),
        source="test",
    )

    context = MarketContext.from_snapshot(snapshot)
    opinion = asyncio.run(provider.generate_opinion(role="market_analyst", context=context))

    assert opinion.agent_id == "mock-market_analyst"
    assert opinion.action == "SELL"
