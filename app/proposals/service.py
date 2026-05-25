import json
import math
from decimal import Decimal

import httpx

from app.core.config import AgentLLMConfig, Settings
from app.core.time import utc_now
from app.market_data.models import AssetType
from app.proposals.models import CandidateScanItem, MarketProposal, ProposalRunRequest, ProposalRunResponse
from app.proposals.universe import infer_asset_type, normalize_symbols
from app.storage.repositories import new_id


class MarketProposalEngine:
    def __init__(self, *, settings: Settings, provider):
        self.settings = settings
        self.provider = provider

    async def run(self, request: ProposalRunRequest) -> ProposalRunResponse:
        symbols = normalize_symbols(request.symbols)
        scanned: list[CandidateScanItem] = []
        for symbol in symbols:
            asset_type = infer_asset_type(symbol)
            snapshot = await self.provider.get_market_snapshot(symbol, asset_type)
            scanned.append(scan_snapshot(snapshot))

        ranked = sorted(scanned, key=lambda item: item.score, reverse=True)
        llm_config = select_proposal_llm(self.settings)
        used_llm = False
        llm_provider = llm_config.provider if llm_config else "rules"
        message = "规则扫描生成候选提案"

        if request.use_llm and llm_config:
            try:
                proposals = await generate_llm_proposals(
                    config=llm_config,
                    scanned=ranked,
                    max_proposals=request.max_proposals,
                    max_notional=request.max_notional,
                )
                used_llm = True
                message = "LLM 提案模型生成候选提案"
            except Exception as exc:
                proposals = rule_based_proposals(ranked, request.max_proposals, request.max_notional)
                message = f"LLM 提案失败，已回退到规则提案：{type(exc).__name__}"
        else:
            proposals = rule_based_proposals(ranked, request.max_proposals, request.max_notional)

        return ProposalRunResponse(
            proposal_run_id=new_id("proposal"),
            created_at=utc_now(),
            candidate_count=len(scanned),
            proposals=proposals,
            scanned=ranked,
            used_llm=used_llm,
            llm_provider=llm_provider,
            message=message,
        )

def scan_snapshot(snapshot) -> CandidateScanItem:
    previous = snapshot.previous_close or snapshot.open or snapshot.price
    change_pct = float((snapshot.price - previous) / previous) if previous and previous > 0 else 0.0
    range_base = snapshot.previous_close or snapshot.price
    intraday_range_pct = (
        float((snapshot.high - snapshot.low) / range_base)
        if snapshot.high is not None and snapshot.low is not None and range_base > 0
        else 0.0
    )
    volume_component = math.log10(max(snapshot.volume or 1, 1)) / 10
    score = abs(change_pct) * 100 + intraday_range_pct * 40 + volume_component
    reasons = [
        f"涨跌幅 {change_pct * 100:.2f}%",
        f"日内区间 {intraday_range_pct * 100:.2f}%",
    ]
    if snapshot.volume is not None:
        reasons.append(f"成交量 {snapshot.volume:,}")

    return CandidateScanItem(
        symbol=snapshot.symbol.upper(),
        asset_type=snapshot.asset_type,
        snapshot=snapshot,
        change_pct=change_pct,
        intraday_range_pct=intraday_range_pct,
        volume=snapshot.volume,
        score=round(score, 4),
        reasons=reasons,
    )


def select_proposal_llm(settings: Settings) -> AgentLLMConfig | None:
    for config in settings.effective_llm_agent_configs():
        if config.enabled and config.provider.lower() != "mock" and config.api_key and config.model:
            return config
    if settings.llm_provider.lower() != "mock" and settings.llm_api_key and settings.llm_model:
        return AgentLLMConfig(
            role="market_analyst",
            provider=settings.llm_provider,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return None


def rule_based_proposals(
    scanned: list[CandidateScanItem],
    max_proposals: int,
    max_notional: Decimal,
) -> list[MarketProposal]:
    proposals: list[MarketProposal] = []
    for rank, item in enumerate(scanned[:max_proposals], start=1):
        if item.change_pct > 0.002:
            action = "BUY"
            thesis = f"{item.symbol} 动量为正，{'; '.join(item.reasons)}，值得提交会议审查。"
        elif item.change_pct < -0.002:
            action = "SELL"
            thesis = f"{item.symbol} 短线走弱，{'; '.join(item.reasons)}，适合提交会议做风险审查。"
        else:
            action = "HOLD"
            thesis = f"{item.symbol} 价格变化有限，{'; '.join(item.reasons)}，仅作为观察提案。"

        proposals.append(
            MarketProposal(
                symbol=item.symbol,
                asset_type=item.asset_type,
                proposed_action=action,  # type: ignore[arg-type]
                confidence=min(0.85, max(0.45, 0.5 + item.score / 20)),
                thesis=thesis,
                risks=["规则提案只基于快照摘要，正式交易仍需会议共识和风控。"],
                suggested_max_notional=max_notional,
                source="rules",
                rank=rank,
                scan_score=item.score,
                raw_payload={"scan": item.model_dump(mode="json")},
            )
        )
    return proposals


async def generate_llm_proposals(
    *,
    config: AgentLLMConfig,
    scanned: list[CandidateScanItem],
    max_proposals: int,
    max_notional: Decimal,
) -> list[MarketProposal]:
    prompt_payload = {
        "max_proposals": max_proposals,
        "max_notional": str(max_notional),
        "candidates": [
            {
                "symbol": item.symbol,
                "asset_type": item.asset_type,
                "price": str(item.snapshot.price),
                "change_pct": item.change_pct,
                "intraday_range_pct": item.intraday_range_pct,
                "volume": item.volume,
                "score": item.score,
                "reasons": item.reasons,
            }
            for item in scanned
        ],
    }
    payload = {
        "model": config.model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a market proposal agent. Select up to max_proposals candidates for a later "
                    "investment conference. Return strict JSON: {\"proposals\":[{\"symbol\",\"proposed_action\","
                    "\"confidence\",\"thesis\",\"risks\"}]}. proposed_action must be BUY, SELL, or HOLD. "
                    "Do not claim these are orders. They are proposals only."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json=payload,
        )
        response.raise_for_status()

    body = response.json()
    content = body["choices"][0]["message"]["content"]
    data = json.loads(content)
    by_symbol = {item.symbol: item for item in scanned}
    proposals: list[MarketProposal] = []
    for rank, raw in enumerate(data.get("proposals", [])[:max_proposals], start=1):
        symbol = str(raw.get("symbol", "")).upper()
        item = by_symbol.get(symbol)
        if item is None:
            continue
        action = raw.get("proposed_action", "HOLD")
        if action not in {"BUY", "SELL", "HOLD"}:
            action = "HOLD"
        proposals.append(
            MarketProposal(
                symbol=item.symbol,
                asset_type=item.asset_type,
                proposed_action=action,
                confidence=min(1.0, max(0.0, float(raw.get("confidence", 0.5)))),
                thesis=str(raw.get("thesis", "")) or f"{item.symbol} 被提案模型选中。",
                risks=[str(risk) for risk in raw.get("risks", [])],
                suggested_max_notional=max_notional,
                source=config.provider,
                rank=rank,
                scan_score=item.score,
                raw_payload={"provider": config.provider, "model": config.model, "body": raw},
            )
        )

    return proposals or rule_based_proposals(scanned, max_proposals, max_notional)
