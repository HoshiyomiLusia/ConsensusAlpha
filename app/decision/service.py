from decimal import Decimal

from sqlalchemy.orm import Session

from app.brokers.models import Position
from app.core.config import Settings
from app.decision.models import DecisionPlan, DecisionPlanItem, PortfolioReviewItem
from app.portfolio.service import get_effective_positions
from app.proposals.models import MarketProposal
from app.storage.repositories import new_id


STOP_LOSS_PCT = Decimal("-0.08")
EXIT_PCT = Decimal("-0.15")
TAKE_PROFIT_PCT = Decimal("0.12")
ADD_PCT = Decimal("0.03")


async def review_portfolio(
    *,
    db: Session,
    settings: Settings,
    provider,
    max_notional: Decimal,
) -> list[PortfolioReviewItem]:
    positions = await get_effective_positions(db=db, settings=settings, provider=provider)
    reviews: list[PortfolioReviewItem] = []
    for position in positions:
        if position.quantity == 0:
            continue
        snapshot = await provider.get_market_snapshot(position.symbol, position.asset_type)
        reviews.append(_review_position(position, snapshot.price, max_notional))
    return sorted(reviews, key=lambda item: item.priority_score, reverse=True)


def review_to_proposal(review: PortfolioReviewItem) -> MarketProposal:
    confidence = min(0.95, max(0.45, review.priority_score / 100))
    return MarketProposal(
        symbol=review.symbol,
        asset_type=review.asset_type,
        proposed_action=review.proposed_action,
        confidence=confidence,
        thesis=review.thesis,
        risks=review.risk_notes,
        suggested_max_notional=review.suggested_max_notional,
        source="portfolio_review",
        rank=0,
        scan_score=review.priority_score,
        raw_payload=review.model_dump(mode="json"),
    )


def choose_plan_proposal(
    *,
    portfolio_reviews: list[PortfolioReviewItem],
    opportunity_proposals: list[MarketProposal],
) -> tuple[MarketProposal, str]:
    actionable_reviews = [
        item for item in portfolio_reviews if item.proposed_action in {"BUY", "SELL"}
    ]
    if actionable_reviews:
        selected_review = actionable_reviews[0]
        return review_to_proposal(selected_review), _intent_label(selected_review.review_action)

    buy_proposal = next(
        (proposal for proposal in opportunity_proposals if proposal.proposed_action == "BUY"),
        None,
    )
    if buy_proposal:
        return buy_proposal, "发现新机会"

    hold_review = next((item for item in portfolio_reviews if item.proposed_action == "HOLD"), None)
    if hold_review:
        return review_to_proposal(hold_review), _intent_label(hold_review.review_action)

    return opportunity_proposals[0], "观察候选"


def build_decision_plan(
    *,
    portfolio_reviews: list[PortfolioReviewItem],
    opportunity_proposals: list[MarketProposal],
    selected: MarketProposal,
    selected_intent: str,
    conference,
) -> DecisionPlan:
    selected_source = (
        "portfolio_review" if selected.source == "portfolio_review" else "opportunity_scan"
    )
    items: list[DecisionPlanItem] = [
        DecisionPlanItem(
            source="portfolio_review",
            symbol=review.symbol,
            asset_type=review.asset_type,
            intent=_intent_label(review.review_action),
            proposed_action=review.proposed_action,
            confidence=min(0.95, max(0.45, review.priority_score / 100)),
            priority_score=review.priority_score,
            thesis=review.thesis,
            suggested_max_notional=review.suggested_max_notional,
        )
        for review in portfolio_reviews
    ]
    items.extend(
        DecisionPlanItem(
            source="opportunity_scan",
            symbol=proposal.symbol,
            asset_type=proposal.asset_type,
            intent="发现新机会" if proposal.proposed_action == "BUY" else "观察候选",
            proposed_action=proposal.proposed_action,
            confidence=proposal.confidence,
            priority_score=proposal.scan_score,
            thesis=proposal.thesis,
            suggested_max_notional=proposal.suggested_max_notional,
        )
        for proposal in opportunity_proposals
    )
    for item in items:
        if item.symbol == selected.symbol and item.source == selected_source:
            item.conference_id = conference.conference_id
            item.final_action = conference.final_action
            item.risk_approved = conference.risk_approved
            item.order_id = conference.order_id
            item.live_preview_id = conference.live_preview_id
            break

    order_required = bool(conference.order_id or conference.live_preview_id)
    if order_required:
        next_step = "进入订单页处理确认"
    elif conference.final_action == "HOLD":
        next_step = "今日无需操作"
    elif not conference.consensus_reached:
        next_step = "会议未达成共识，今日不执行"
    elif not conference.risk_approved:
        next_step = "风控阻断，今日不执行"
    else:
        next_step = "无需处理订单"

    summary = _plan_summary(
        symbol=selected.symbol,
        intent=selected_intent,
        final_action=conference.final_action,
        order_required=order_required,
        risk_approved=conference.risk_approved,
    )
    return DecisionPlan(
        plan_id=new_id("plan"),
        summary=summary,
        next_step=next_step,
        selected_source=selected_source,
        selected_symbol=selected.symbol,
        selected_intent=selected_intent,
        final_action=conference.final_action,
        order_required=order_required,
        risk_approved=conference.risk_approved,
        order_id=conference.order_id,
        live_preview_id=conference.live_preview_id,
        portfolio_review_count=len(portfolio_reviews),
        opportunity_count=len(opportunity_proposals),
        items=items,
    )


def _review_position(
    position: Position,
    last_price: Decimal,
    max_notional: Decimal,
) -> PortfolioReviewItem:
    quantity = abs(position.quantity)
    current_value = (quantity * last_price).copy_abs()
    average_price = position.average_price
    pnl_pct = (
        (last_price - average_price) / average_price
        if average_price > 0
        else Decimal("0")
    )

    if pnl_pct <= EXIT_PCT:
        action = "EXIT"
        proposed = "SELL"
        priority = 112 + min(10, abs(float(pnl_pct)) * 50)
        thesis = f"{position.symbol} 亏损显著扩大，提交会议判断是否清仓退出。"
        notes = ["严重亏损触发清仓复盘，优先于普通止损和新机会。"]
        suggested = min(current_value, max_notional)
    elif pnl_pct <= STOP_LOSS_PCT:
        action = "STOP_LOSS"
        proposed = "SELL"
        priority = 95 + min(20, abs(float(pnl_pct)) * 100)
        thesis = f"{position.symbol} 跌幅触发止损复盘，优先提交会议判断是否卖出。"
        notes = ["持仓亏损达到止损阈值，先于新机会处理。"]
        suggested = min(current_value, max_notional)
    elif pnl_pct >= TAKE_PROFIT_PCT:
        action = "TAKE_PROFIT"
        proposed = "SELL"
        priority = 80 + min(15, float(pnl_pct) * 50)
        thesis = f"{position.symbol} 浮盈较高，提交会议判断是否止盈或减仓。"
        notes = ["盈利达到止盈观察阈值，避免利润回撤。"]
        suggested = min(current_value / Decimal("2"), max_notional)
    elif current_value > max_notional * Decimal("3"):
        action = "REDUCE"
        proposed = "SELL"
        priority = 70
        thesis = f"{position.symbol} 仓位相对单次预算偏大，提交会议判断是否减仓。"
        notes = ["仓位集中度偏高，降低组合波动。"]
        suggested = min(current_value / Decimal("3"), max_notional)
    elif pnl_pct >= ADD_PCT:
        action = "ADD"
        proposed = "BUY"
        priority = 55 + min(15, float(pnl_pct) * 100)
        thesis = f"{position.symbol} 持仓表现为正，提交会议判断是否加仓。"
        notes = ["加仓仍受账户资金、仓位上限和冷却期限制。"]
        suggested = max_notional
    else:
        action = "KEEP"
        proposed = "HOLD"
        priority = 20 + min(10, abs(float(pnl_pct)) * 50)
        thesis = f"{position.symbol} 未触发止损、止盈或仓位调整条件，默认继续持有。"
        notes = ["继续持有不生成订单。"]
        suggested = Decimal("0")

    return PortfolioReviewItem(
        symbol=position.symbol.upper(),
        asset_type=position.asset_type,  # type: ignore[arg-type]
        quantity=position.quantity,
        average_price=average_price,
        market_value=current_value,
        last_price=last_price,
        unrealized_pnl_pct=pnl_pct,
        review_action=action,  # type: ignore[arg-type]
        proposed_action=proposed,  # type: ignore[arg-type]
        priority_score=round(priority, 4),
        thesis=thesis,
        risk_notes=notes,
        suggested_max_notional=suggested,
    )


def _intent_label(action: str) -> str:
    return {
        "KEEP": "继续持有",
        "ADD": "加仓复盘",
        "REDUCE": "减仓复盘",
        "EXIT": "清仓复盘",
        "STOP_LOSS": "止损复盘",
        "TAKE_PROFIT": "止盈复盘",
    }.get(action, "组合复盘")


def _plan_summary(
    *,
    symbol: str,
    intent: str,
    final_action: str,
    order_required: bool,
    risk_approved: bool,
) -> str:
    if order_required:
        return f"{symbol} {intent} 后形成 {final_action} 计划，等待用户处理订单。"
    if final_action == "HOLD":
        return f"{symbol} {intent} 后结论为观望，今日不需要操作。"
    if not risk_approved:
        return f"{symbol} {intent} 后结论为 {final_action}，但风控阻断。"
    return f"{symbol} {intent} 后结论为 {final_action}，未生成订单。"
