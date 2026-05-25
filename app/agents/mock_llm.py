from app.agents.roles import CHAIRPERSON_ROLE
from app.conference.models import AgentOpinion
from app.market_data.models import MarketSnapshot


class MockLLMProvider:
    """Predictable agent provider for local development and deterministic tests."""

    def __init__(self, default_action: str | None = None):
        self.default_action = default_action or None
        self._usage_events: list[dict] = []

    async def generate_opinion(
        self,
        *,
        role: str,
        snapshot: MarketSnapshot,
        requested_action: str | None = None,
    ) -> AgentOpinion:
        action = requested_action or self.default_action
        if not action:
            action = "HOLD" if role == "contrarian_critic" else "BUY"
        if role == CHAIRPERSON_ROLE:
            action = "HOLD"

        blocking_concerns: list[str] = []
        concerns: list[str] = []
        confidence = 0.82
        if role == "contrarian_critic" and action == "HOLD":
            concerns.append("mock critic requires stronger confirmation")

        opinion = AgentOpinion(
            agent_id=f"mock-{role}",
            role=role,
            symbol=snapshot.symbol,
            action=action,  # type: ignore[arg-type]
            confidence=confidence,
            thesis=f"Mock {role} review for {snapshot.symbol} at {snapshot.price}.",
            concerns=concerns,
            blocking_concerns=blocking_concerns,
            suggested_max_position_pct=0.05 if role == "risk_manager" else None,
            suggested_stop_loss_pct=0.05 if role == "risk_manager" else None,
            raw_payload={"provider": "mock", "role": role, "action": action},
        )
        self._record_estimated_usage(
            role=role,
            operation="opinion",
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
            prompt=votes,
            completion=summary,
        )
        return summary

    def consume_usage_events(self) -> list[dict]:
        events = list(self._usage_events)
        self._usage_events.clear()
        return events

    def _record_estimated_usage(self, *, role: str, operation: str, prompt: str, completion: str) -> None:
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
                "raw_payload": {"method": "character_estimate"},
            }
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, (len(text) + 3) // 4)
