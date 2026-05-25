from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.brokers.models import OrderIntent
from app.execution.paper import PaperExecutor
from app.market_data.models import MarketSnapshot
from app.storage.tables import Base, PaperOrderTable


def test_paper_executor_creates_filled_order():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True)

    with session_factory() as db:
        order = OrderIntent(
            client_order_id="client-test",
            symbol="AAPL",
            side="BUY",
            quantity=Decimal("2"),
            notional=Decimal("200"),
        )
        snapshot = MarketSnapshot(
            symbol="AAPL",
            asset_type="equity",
            price=Decimal("100"),
            timestamp=datetime.now(UTC),
            source="test",
        )
        execution = PaperExecutor().execute(
            db=db,
            conference_id="conf-test",
            order=order,
            snapshot=snapshot,
        )
        db.commit()

        row = db.get(PaperOrderTable, execution.order_id)
        assert row is not None
        assert row.status == "FILLED"
        assert row.notional == "200"
        assert execution.status == "FILLED"
