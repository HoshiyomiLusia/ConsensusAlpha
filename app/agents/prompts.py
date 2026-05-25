from dataclasses import dataclass

from app.agents.roles import ALL_AGENT_ROLES, CHAIRPERSON_ROLE


PROMPT_VERSION_ID = "2026-05-25-v1"

ROLE_GUIDANCE = {
    "market_analyst": (
        "Focus on multi-timeframe price action, trend structure, momentum, "
        "MACD/RSI behavior, and where price sits inside Bollinger bands."
    ),
    "risk_manager": (
        "Focus on realized volatility, ATR-implied stop distance, liquidity, "
        "position sizing, and downside scenarios. Raise blocking_concerns if "
        "the trade is structurally unsafe."
    ),
    "contrarian_critic": (
        "Argue against the trade. Look for trend exhaustion, divergences, "
        "stretched RSI, weak relative strength, and overcrowded setups."
    ),
    "execution_specialist": (
        "Focus on liquidity, relative_volume, spread, time-of-day, and the "
        "appropriate order type. Flag execution-time concerns."
    ),
    CHAIRPERSON_ROLE: "Summarize the conference result without changing agent votes.",
}

PROMPT_VERSIONS = {role: PROMPT_VERSION_ID for role in ALL_AGENT_ROLES}


@dataclass(frozen=True)
class RolePrompt:
    role: str
    version: str
    system: str


def prompt_version_for(role: str) -> str:
    return PROMPT_VERSIONS.get(role, PROMPT_VERSION_ID)


def opinion_prompt_for(role: str) -> RolePrompt:
    role_hint = ROLE_GUIDANCE.get(role, "")
    return RolePrompt(
        role=role,
        version=prompt_version_for(role),
        system=(
            f"You are an investment conference agent playing the role of {role}. "
            f"{role_hint} "
            "You receive a structured MarketContext with multi-timeframe technical "
            "features, a liquidity profile, and relative-strength readings. "
            "Reason from these features, not from raw price alone. "
            "Return strict JSON with keys: agent_id, role, symbol, action, "
            "confidence, thesis, concerns, blocking_concerns, "
            "suggested_max_position_pct, suggested_stop_loss_pct. "
            "action must be BUY, SELL, or HOLD. concerns and blocking_concerns "
            "are arrays of short strings. confidence is a float in [0, 1]."
        ),
    )


def summary_prompt() -> RolePrompt:
    return RolePrompt(
        role=CHAIRPERSON_ROLE,
        version=prompt_version_for(CHAIRPERSON_ROLE),
        system="Summarize this investment conference in one concise paragraph.",
    )
