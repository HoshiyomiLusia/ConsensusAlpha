from datetime import UTC, datetime

from app.conference.consensus import evaluate_consensus
from app.conference.models import AgentOpinion


def _opinion(role: str, action: str = "BUY", confidence: float = 0.8, blocking=None):
    return AgentOpinion(
        agent_id=f"agent-{role}",
        role=role,
        symbol="AAPL",
        action=action,
        confidence=confidence,
        thesis="test",
        blocking_concerns=blocking or [],
    )


def _evaluate(opinions):
    now = datetime.now(UTC)
    return evaluate_consensus(
        conference_id="conf-test",
        symbol="AAPL",
        started_at=now,
        completed_at=now,
        opinions=opinions,
        min_confidence=0.65,
    )


def test_consensus_unanimous_buy_passes():
    result = _evaluate(
        [
            _opinion("market_analyst"),
            _opinion("risk_manager"),
            _opinion("contrarian_critic"),
            _opinion("execution_specialist"),
            _opinion("chairperson", "HOLD"),
        ]
    )

    assert result.consensus_reached is True
    assert result.final_action == "BUY"


def test_consensus_disagreement_holds():
    result = _evaluate(
        [
            _opinion("market_analyst", "BUY"),
            _opinion("risk_manager", "BUY"),
            _opinion("contrarian_critic", "HOLD"),
            _opinion("execution_specialist", "BUY"),
        ]
    )

    assert result.consensus_reached is False
    assert result.final_action == "HOLD"
    assert result.consensus_reason == "agents disagree"


def test_consensus_blocking_concern_holds():
    result = _evaluate(
        [
            _opinion("market_analyst"),
            _opinion("risk_manager"),
            _opinion("contrarian_critic", blocking=["liquidity gap"]),
            _opinion("execution_specialist"),
        ]
    )

    assert result.final_action == "HOLD"
    assert result.consensus_reason == "blocking concern raised"


def test_consensus_low_confidence_holds():
    result = _evaluate(
        [
            _opinion("market_analyst"),
            _opinion("risk_manager"),
            _opinion("contrarian_critic", confidence=0.5),
            _opinion("execution_specialist"),
        ]
    )

    assert result.final_action == "HOLD"
    assert result.consensus_reason == "confidence below threshold"
