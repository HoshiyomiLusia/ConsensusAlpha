from datetime import datetime

from app.agents.roles import REQUIRED_AGENT_ROLES
from app.conference.models import AgentOpinion, ConferenceResult


def evaluate_consensus(
    *,
    conference_id: str,
    symbol: str,
    started_at: datetime,
    completed_at: datetime,
    opinions: list[AgentOpinion],
    min_confidence: float,
    chairperson_summary: str = "",
) -> ConferenceResult:
    required = [opinion for opinion in opinions if opinion.role in REQUIRED_AGENT_ROLES]
    required_roles = {opinion.role for opinion in required}

    def hold(reason: str) -> ConferenceResult:
        return ConferenceResult(
            conference_id=conference_id,
            symbol=symbol,
            started_at=started_at,
            completed_at=completed_at,
            opinions=opinions,
            final_action="HOLD",
            consensus_reached=False,
            consensus_reason=reason,
            chairperson_summary=chairperson_summary,
        )

    if required_roles != REQUIRED_AGENT_ROLES:
        missing = sorted(REQUIRED_AGENT_ROLES - required_roles)
        return hold(f"missing required agent opinion: {', '.join(missing)}")

    if any(opinion.blocking_concerns for opinion in required):
        return hold("blocking concern raised")

    if any(opinion.confidence < min_confidence for opinion in required):
        return hold("confidence below threshold")

    risk_manager = next(opinion for opinion in required if opinion.role == "risk_manager")
    if risk_manager.action == "HOLD" or risk_manager.blocking_concerns:
        return hold("risk manager veto")

    actions = {opinion.action for opinion in required}
    if len(actions) != 1:
        return hold("agents disagree")

    action = actions.pop()
    if action == "HOLD":
        return hold("unanimous hold")

    return ConferenceResult(
        conference_id=conference_id,
        symbol=symbol,
        started_at=started_at,
        completed_at=completed_at,
        opinions=opinions,
        final_action=action,
        consensus_reached=True,
        consensus_reason=f"all required agents approved {action}",
        chairperson_summary=chairperson_summary,
    )
