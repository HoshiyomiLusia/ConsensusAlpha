from decimal import Decimal, ROUND_DOWN

from sqlalchemy.orm import Session

from app.agents.roles import ALL_AGENT_ROLES, CHAIRPERSON_ROLE
from app.brokers.models import OrderIntent
from app.conference.consensus import evaluate_consensus
from app.conference.models import ConferenceRunRequest, ConferenceRunResponse
from app.core.config import Settings
from app.core.time import utc_now
from app.execution.paper import PaperExecutor
from app.risk.models import RiskInput
from app.risk.service import RiskService
from app.storage.repositories import (
    new_id,
    save_model_usage_events,
    save_opinions,
    save_risk_decision,
    save_snapshot,
)
from app.storage.tables import ConferenceRunTable, ConsensusResultTable, LiveOrderPreviewTable


class ConferenceOrchestrator:
    def __init__(self, *, settings: Settings, provider, llm_provider):
        self.settings = settings
        self.provider = provider
        self.llm_provider = llm_provider
        self.risk_service = RiskService(settings)
        self.paper_executor = PaperExecutor()

    async def run(self, *, db: Session, request: ConferenceRunRequest) -> ConferenceRunResponse:
        conference_id = new_id("conf")
        started_at = utc_now()
        snapshot = await self.provider.get_market_snapshot(request.symbol, request.asset_type)
        snapshot_row = save_snapshot(db, snapshot)

        run_row = ConferenceRunTable(
            id=conference_id,
            symbol=request.symbol.upper(),
            snapshot_id=snapshot_row.id,
            started_at=started_at,
            context_payload={
                "request": request.model_dump(mode="json"),
                "snapshot": snapshot.model_dump(mode="json"),
                "settings": self.settings.redacted(),
            },
        )
        db.add(run_row)
        db.flush()

        opinions = []
        for role in ALL_AGENT_ROLES:
            opinion = await self.llm_provider.generate_opinion(
                role=role,
                snapshot=snapshot,
                requested_action=request.mock_agent_action,
            )
            opinions.append(opinion)
        chairperson_summary = await self.llm_provider.summarize(
            [opinion for opinion in opinions if opinion.role != CHAIRPERSON_ROLE]
        )
        usage_events = self._consume_usage_events()
        completed_at = utc_now()
        consensus = evaluate_consensus(
            conference_id=conference_id,
            symbol=request.symbol.upper(),
            started_at=started_at,
            completed_at=completed_at,
            opinions=opinions,
            min_confidence=self.settings.min_agent_confidence,
            chairperson_summary=chairperson_summary,
        )
        save_opinions(db, conference_id, opinions)
        save_model_usage_events(db, conference_id, usage_events)
        db.add(
            ConsensusResultTable(
                id=new_id("consensus"),
                conference_id=conference_id,
                final_action=consensus.final_action,
                consensus_reached=consensus.consensus_reached,
                reason=consensus.consensus_reason,
                raw_payload=consensus.model_dump(mode="json"),
            )
        )

        order_id: str | None = None
        live_preview_id: str | None = None
        quantity = self._quantity_for_notional(request.max_notional, snapshot.price)
        suggested_stop_loss_pct = self._risk_manager_stop_loss(opinions)

        if consensus.final_action == "HOLD":
            risk_decision = self.risk_service.evaluate(
                db=db,
                risk_input=RiskInput(
                    symbol=request.symbol.upper(),
                    action="HOLD",
                    trading_mode=self.settings.trading_mode,
                    price=snapshot.price,
                    requested_notional=request.max_notional,
                    requested_quantity=quantity,
                    order_type=request.order_type,
                    limit_price=request.limit_price,
                    suggested_stop_loss_pct=suggested_stop_loss_pct,
                ),
                account=None,
                positions=[],
            )
        else:
            account = await self.provider.get_account_summary()
            positions = await self.provider.get_positions()
            risk_decision = self.risk_service.evaluate(
                db=db,
                risk_input=RiskInput(
                    symbol=request.symbol.upper(),
                    action=consensus.final_action,
                    trading_mode=self.settings.trading_mode,
                    price=snapshot.price,
                    requested_notional=request.max_notional,
                    requested_quantity=quantity,
                    order_type=request.order_type,
                    limit_price=request.limit_price,
                    suggested_stop_loss_pct=suggested_stop_loss_pct,
                ),
                account=account,
                positions=positions,
            )

        risk_row = save_risk_decision(db, conference_id=conference_id, decision=risk_decision)
        if risk_decision.approved and consensus.final_action in {"BUY", "SELL"}:
            order_intent = OrderIntent(
                client_order_id=new_id("client"),
                symbol=request.symbol.upper(),
                asset_type=request.asset_type,  # type: ignore[arg-type]
                side=consensus.final_action,  # type: ignore[arg-type]
                quantity=quantity,
                order_type=request.order_type,
                limit_price=request.limit_price,
                notional=request.max_notional,
            )
            if self.settings.trading_mode == "live":
                preview = await self.provider.preview_order(order_intent)
                preview_id = new_id("preview")
                db.add(
                    LiveOrderPreviewTable(
                        id=preview_id,
                        client_order_id=order_intent.client_order_id,
                        conference_id=conference_id,
                        risk_decision_id=risk_row.id,
                        symbol=order_intent.symbol,
                        side=order_intent.side,
                        quantity=str(order_intent.quantity),
                        order_type=order_intent.order_type,
                        limit_price=str(order_intent.limit_price) if order_intent.limit_price else None,
                        estimated_notional=str(preview.estimated_notional)
                        if preview.estimated_notional is not None
                        else str(request.max_notional),
                        status="PENDING_CONFIRMATION",
                        account_id=preview.account_id,
                        environment=preview.environment,
                        preview_payload=preview.model_dump(mode="json"),
                    )
                )
                live_preview_id = preview_id
            else:
                execution = self.paper_executor.execute(
                    db=db,
                    conference_id=conference_id,
                    order=order_intent,
                    snapshot=snapshot,
                )
                order_id = execution.order_id

        run_row.completed_at = completed_at
        run_row.final_action = consensus.final_action
        run_row.consensus_reached = consensus.consensus_reached
        run_row.consensus_reason = consensus.consensus_reason
        run_row.chairperson_summary = chairperson_summary
        run_row.risk_decision_id = risk_row.id
        run_row.order_id = order_id
        run_row.live_preview_id = live_preview_id
        db.commit()

        return ConferenceRunResponse(
            conference_id=conference_id,
            symbol=request.symbol.upper(),
            final_action=consensus.final_action,
            consensus_reached=consensus.consensus_reached,
            risk_approved=risk_decision.approved,
            order_id=order_id,
            live_preview_id=live_preview_id,
        )

    @staticmethod
    def _quantity_for_notional(max_notional: Decimal, price: Decimal) -> Decimal:
        return (max_notional / price).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)

    @staticmethod
    def _risk_manager_stop_loss(opinions) -> float | None:
        for opinion in opinions:
            if opinion.role == "risk_manager":
                return opinion.suggested_stop_loss_pct
        return None

    def _consume_usage_events(self) -> list[dict]:
        consume = getattr(self.llm_provider, "consume_usage_events", None)
        if not consume:
            return []
        return consume()
