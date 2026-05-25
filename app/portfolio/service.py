from decimal import Decimal

from sqlalchemy.orm import Session

from app.brokers.models import AccountSummary, Position
from app.core.config import Settings
from app.proposals.universe import infer_asset_type
from app.storage.repositories import list_paper_positions
from app.storage.tables import PaperPositionTable


def paper_position_to_model(row: PaperPositionTable) -> Position:
    quantity = Decimal(row.quantity)
    return Position(
        symbol=row.symbol.upper(),
        asset_type=infer_asset_type(row.symbol),
        quantity=quantity,
        average_price=Decimal(row.average_price),
        market_value=Decimal(row.market_value),
        side="SHORT" if quantity < 0 else "LONG",
        raw_payload={"provider": "paper", "position_id": row.id},
    )


async def get_effective_positions(*, db: Session, settings: Settings, provider) -> list[Position]:
    if settings.trading_mode == "paper":
        return [
            paper_position_to_model(row)
            for row in list_paper_positions(db)
            if Decimal(row.quantity) != 0
        ]
    return await provider.get_positions()


async def get_effective_account(*, db: Session, settings: Settings, provider) -> AccountSummary:
    account = await provider.get_account_summary()
    if settings.trading_mode != "paper":
        return account

    positions = [
        paper_position_to_model(row)
        for row in list_paper_positions(db)
        if Decimal(row.quantity) != 0
    ]
    invested = sum(abs(position.market_value) for position in positions)
    return AccountSummary(
        account_id=account.account_id,
        equity=account.equity,
        buying_power=account.buying_power,
        cash=account.cash,
        currency=account.currency,
        raw_payload={
            **account.raw_payload,
            "paper_position_notional": str(invested),
            "effective_source": "paper_positions",
        },
    )
