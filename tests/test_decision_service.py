from decimal import Decimal

from app.decision.models import PortfolioReviewItem
from app.decision.service import choose_plan_proposal
from app.proposals.models import MarketProposal


def _review(symbol: str, action: str = "KEEP", proposed_action: str = "HOLD") -> PortfolioReviewItem:
    return PortfolioReviewItem(
        symbol=symbol,
        asset_type="etf",
        quantity=Decimal("10"),
        average_price=Decimal("100"),
        market_value=Decimal("1000"),
        last_price=Decimal("100"),
        unrealized_pnl_pct=Decimal("0"),
        review_action=action,
        proposed_action=proposed_action,
        priority_score=20,
        thesis="test review",
        risk_notes=[],
        suggested_max_notional=Decimal("0"),
    )


def _proposal(symbol: str, rank: int, action: str = "BUY") -> MarketProposal:
    return MarketProposal(
        symbol=symbol,
        asset_type="etf",
        proposed_action=action,
        confidence=0.7,
        thesis="test proposal",
        risks=[],
        suggested_max_notional=Decimal("1000"),
        source="rules",
        rank=rank,
        scan_score=10 - rank,
    )


def test_choose_plan_prefers_fresh_buy_candidate_over_existing_hold_position():
    selected, intent = choose_plan_proposal(
        portfolio_reviews=[_review("IWM")],
        opportunity_proposals=[_proposal("IWM", 1), _proposal("DIA", 2)],
    )

    assert selected.symbol == "DIA"
    assert intent == "发现新机会"


def test_choose_plan_still_prioritizes_actionable_portfolio_review():
    selected, intent = choose_plan_proposal(
        portfolio_reviews=[_review("IWM", action="STOP_LOSS", proposed_action="SELL")],
        opportunity_proposals=[_proposal("DIA", 1)],
    )

    assert selected.symbol == "IWM"
    assert selected.proposed_action == "SELL"
    assert intent == "止损复盘"
