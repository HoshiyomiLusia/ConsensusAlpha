from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


JSONType = JSON


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MarketSnapshotTable(TimestampMixin, Base):
    __tablename__ = "market_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    price: Mapped[str] = mapped_column(String(64))
    open: Mapped[str | None] = mapped_column(String(64))
    high: Mapped[str | None] = mapped_column(String(64))
    low: Mapped[str | None] = mapped_column(String(64))
    previous_close: Mapped[str | None] = mapped_column(String(64))
    volume: Mapped[int | None] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class ConferenceRunTable(TimestampMixin, Base):
    __tablename__ = "conference_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("market_snapshots.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_action: Mapped[str] = mapped_column(String(8), default="HOLD")
    consensus_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    consensus_reason: Mapped[str] = mapped_column(Text, default="")
    chairperson_summary: Mapped[str] = mapped_column(Text, default="")
    context_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    risk_decision_id: Mapped[str | None] = mapped_column(String(64))
    order_id: Mapped[str | None] = mapped_column(String(64))
    live_preview_id: Mapped[str | None] = mapped_column(String(64))


class AgentOpinionTable(TimestampMixin, Base):
    __tablename__ = "agent_opinions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conference_id: Mapped[str] = mapped_column(ForeignKey("conference_runs.id"), index=True)
    agent_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float)
    thesis: Mapped[str] = mapped_column(Text)
    concerns: Mapped[list] = mapped_column(JSONType, default=list)
    blocking_concerns: Mapped[list] = mapped_column(JSONType, default=list)
    suggested_max_position_pct: Mapped[float | None] = mapped_column(Float)
    suggested_stop_loss_pct: Mapped[float | None] = mapped_column(Float)
    prompt_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class ConsensusResultTable(TimestampMixin, Base):
    __tablename__ = "consensus_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conference_id: Mapped[str] = mapped_column(ForeignKey("conference_runs.id"), index=True)
    final_action: Mapped[str] = mapped_column(String(8))
    consensus_reached: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class RiskDecisionTable(TimestampMixin, Base):
    __tablename__ = "risk_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conference_id: Mapped[str | None] = mapped_column(ForeignKey("conference_runs.id"), index=True)
    approved: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    max_quantity: Mapped[str | None] = mapped_column(String(64))
    max_notional: Mapped[str | None] = mapped_column(String(64))
    checks_payload: Mapped[list] = mapped_column(JSONType, default=list)


class RiskCheckTable(TimestampMixin, Base):
    __tablename__ = "risk_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    risk_decision_id: Mapped[str] = mapped_column(ForeignKey("risk_decisions.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    passed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)


class ProposalRunTable(TimestampMixin, Base):
    __tablename__ = "proposal_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_count: Mapped[int] = mapped_column(Integer)
    proposal_count: Mapped[int] = mapped_column(Integer)
    used_llm: Mapped[bool] = mapped_column(Boolean)
    llm_provider: Mapped[str] = mapped_column(String(80))
    request_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    scan_payload: Mapped[list] = mapped_column(JSONType, default=list)
    message: Mapped[str] = mapped_column(Text, default="")


class ProposalItemTable(TimestampMixin, Base):
    __tablename__ = "proposal_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    proposal_run_id: Mapped[str] = mapped_column(ForeignKey("proposal_runs.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    proposed_action: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float)
    thesis: Mapped[str] = mapped_column(Text)
    risks: Mapped[list] = mapped_column(JSONType, default=list)
    suggested_max_notional: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(80))
    rank: Mapped[int] = mapped_column(Integer)
    scan_score: Mapped[float] = mapped_column(Float)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class PaperOrderTable(TimestampMixin, Base):
    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    conference_id: Mapped[str | None] = mapped_column(ForeignKey("conference_runs.id"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[str] = mapped_column(String(64))
    order_type: Mapped[str] = mapped_column(String(16))
    limit_price: Mapped[str | None] = mapped_column(String(64))
    fill_price: Mapped[str] = mapped_column(String(64))
    notional: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(16), default="paper")
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class PaperFillTable(TimestampMixin, Base):
    __tablename__ = "paper_fills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[str] = mapped_column(String(64))
    price: Mapped[str] = mapped_column(String(64))
    notional: Mapped[str] = mapped_column(String(64))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperPositionTable(TimestampMixin, Base):
    __tablename__ = "paper_positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    quantity: Mapped[str] = mapped_column(String(64))
    average_price: Mapped[str] = mapped_column(String(64))
    market_value: Mapped[str] = mapped_column(String(64))


class LiveOrderPreviewTable(TimestampMixin, Base):
    __tablename__ = "live_order_previews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    conference_id: Mapped[str | None] = mapped_column(ForeignKey("conference_runs.id"))
    risk_decision_id: Mapped[str | None] = mapped_column(ForeignKey("risk_decisions.id"))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[str] = mapped_column(String(64))
    order_type: Mapped[str] = mapped_column(String(16))
    limit_price: Mapped[str | None] = mapped_column(String(64))
    estimated_notional: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="PENDING_CONFIRMATION")
    account_id: Mapped[str] = mapped_column(String(80))
    environment: Mapped[str] = mapped_column(String(32))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preview_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class LiveOrderAttemptTable(TimestampMixin, Base):
    __tablename__ = "live_order_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    preview_id: Mapped[str] = mapped_column(ForeignKey("live_order_previews.id"), index=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32))
    request_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    error_payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class AuditEventTable(TimestampMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), index=True)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class ModelUsageEventTable(TimestampMixin, Base):
    __tablename__ = "model_usage_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conference_id: Mapped[str] = mapped_column(ForeignKey("conference_runs.id"), index=True)
    role: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
