from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers.models import OrderIntent
from app.core.time import utc_now
from app.execution.models import ExecutionOrder
from app.market_data.models import MarketSnapshot
from app.storage.repositories import new_id
from app.storage.tables import PaperFillTable, PaperOrderTable, PaperPositionTable


class PaperExecutor:
    def execute(
        self,
        *,
        db: Session,
        conference_id: str | None,
        order: OrderIntent,
        snapshot: MarketSnapshot,
    ) -> ExecutionOrder:
        fill_price = order.limit_price if order.order_type == "LIMIT" and order.limit_price else snapshot.price
        notional = fill_price * order.quantity
        order_id = new_id("paper")
        now = utc_now()
        db.add(
            PaperOrderTable(
                id=order_id,
                client_order_id=order.client_order_id,
                conference_id=conference_id,
                symbol=order.symbol.upper(),
                side=order.side,
                quantity=str(order.quantity),
                order_type=order.order_type,
                limit_price=str(order.limit_price) if order.limit_price else None,
                fill_price=str(fill_price),
                notional=str(notional),
                status="FILLED",
                mode="paper",
                raw_payload={
                    "order": order.model_dump(mode="json"),
                    "snapshot": snapshot.model_dump(mode="json"),
                },
            )
        )
        db.add(
            PaperFillTable(
                id=new_id("fill"),
                order_id=order_id,
                symbol=order.symbol.upper(),
                side=order.side,
                quantity=str(order.quantity),
                price=str(fill_price),
                notional=str(notional),
                filled_at=now,
            )
        )
        self._update_position(db, order.symbol.upper(), order.side, order.quantity, fill_price)
        db.flush()
        return ExecutionOrder(
            order_id=order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            status="FILLED",
            mode="paper",
            created_at=now,
            raw_payload={"fill_price": str(fill_price), "notional": str(notional)},
        )

    def _update_position(self, db: Session, symbol: str, side: str, quantity: Decimal, price: Decimal) -> None:
        row = db.scalar(select(PaperPositionTable).where(PaperPositionTable.symbol == symbol))
        signed_quantity = quantity if side == "BUY" else -quantity
        if row is None:
            db.add(
                PaperPositionTable(
                    id=new_id("pos"),
                    symbol=symbol,
                    quantity=str(signed_quantity),
                    average_price=str(price),
                    market_value=str(signed_quantity * price),
                )
            )
            return

        old_qty = Decimal(row.quantity)
        old_avg = Decimal(row.average_price)
        new_qty = old_qty + signed_quantity
        if new_qty == 0:
            row.quantity = "0"
            row.average_price = "0"
            row.market_value = "0"
            return
        if side == "BUY" and old_qty >= 0:
            row.average_price = str(((old_qty * old_avg) + (quantity * price)) / new_qty)
        row.quantity = str(new_qty)
        row.market_value = str(new_qty * price)
