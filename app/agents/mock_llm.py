from app.agents.roles import CHAIRPERSON_ROLE
from app.agents.prompts import prompt_version_for
from app.conference.models import AgentOpinion
from app.market_data.models import MarketContext


class MockLLMProvider:
    """Predictable agent provider for local development and deterministic tests.

    Action logic is intentionally simple so consensus tests stay stable. The
    feature-rich MarketContext is reflected only in the thesis text and the
    concerns list, so we can verify the data is flowing without changing
    consensus behavior.
    """

    def __init__(self, default_action: str | None = None):
        self.default_action = default_action or None
        self._usage_events: list[dict] = []

    async def generate_opinion(
        self,
        *,
        role: str,
        context: MarketContext,
        requested_action: str | None = None,
    ) -> AgentOpinion:
        action = requested_action or self.default_action
        if not action:
            action = "HOLD" if role == "contrarian_critic" else "BUY"
        if role == CHAIRPERSON_ROLE:
            action = "HOLD"

        snapshot = context.snapshot
        primary = context.primary_timeframe
        thesis_bits = [f"Mock {role} review for {snapshot.symbol} at {snapshot.price}."]
        concerns: list[str] = []

        if primary is not None and primary.bar_count > 0:
            thesis_bits.append(
                f"Primary {primary.interval} trend={primary.trend}"
                + (f", RSI14={primary.rsi_14}" if primary.rsi_14 is not None else "")
                + (f", momentum20={primary.momentum_20}" if primary.momentum_20 is not None else "")
                + "."
            )
            if primary.rsi_14 is not None and primary.rsi_14 >= 75:
                concerns.append(f"RSI elevated at {primary.rsi_14}")
            elif primary.rsi_14 is not None and primary.rsi_14 <= 25:
                concerns.append(f"RSI depressed at {primary.rsi_14}")

        if role == "contrarian_critic" and action == "HOLD":
            concerns.append("mock critic requires stronger confirmation")

        opinion = AgentOpinion(
            agent_id=f"mock-{role}",
            role=role,
            symbol=snapshot.symbol,
            action=action,  # type: ignore[arg-type]
            confidence=0.82,
            thesis=" ".join(thesis_bits),
            concerns=concerns,
            blocking_concerns=[],
            suggested_max_position_pct=0.05 if role == "risk_manager" else None,
            suggested_stop_loss_pct=0.05 if role == "risk_manager" else None,
            prompt_version=prompt_version_for(role),
            raw_payload={
                "provider": "mock",
                "role": role,
                "action": action,
                "prompt_version": prompt_version_for(role),
            },
        )
        self._record_estimated_usage(
            role=role,
            operation="opinion",
            prompt_version=prompt_version_for(role),
            prompt=f"{role} {snapshot.model_dump(mode='json')} {requested_action or ''}",
            completion=opinion.thesis,
        )
        return opinion

    async def summarize(self, opinions: list[AgentOpinion]) -> str:
        votes = ", ".join(f"{opinion.role}:{opinion.action}" for opinion in opinions)
        summary = f"Mock chairperson summary. Votes: {votes}."
        self._record_estimated_usage(
            role=CHAIRPERSON_ROLE,
            operation="summary",
            prompt_version=prompt_version_for(CHAIRPERSON_ROLE),
            prompt=votes,
            completion=summary,
        )
        return summary

    def consume_usage_events(self) -> list[dict]:
        events = list(self._usage_events)
        self._usage_events.clear()
        return events

    def _record_estimated_usage(
        self,
        *,
        role: str,
        operation: str,
        prompt_version: str,
        prompt: str,
        completion: str,
    ) -> None:
        prompt_tokens = self._estimate_tokens(prompt)
        completion_tokens = self._estimate_tokens(completion)
        self._usage_events.append(
            {
                "role": role,
                "operation": operation,
                "provider": "mock",
                "model": "mock",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "estimated": True,
                "prompt_version": prompt_version,
                "raw_payload": {"method": "character_estimate"},
            }
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, (len(text) + 3) // 4)
