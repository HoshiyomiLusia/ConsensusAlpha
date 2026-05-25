import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.brokers.mock_provider import MockBrokerProvider
from app.market_data.features import (
    atr,
    bollinger,
    classify_trend,
    compute_liquidity,
    compute_market_context,
    compute_timeframe_features,
    ema,
    macd,
    momentum,
    rsi,
    sma,
    vwap,
)
from app.market_data.models import HistoricalBar, MarketSnapshot


def _bar(idx: int, close: float, volume: int = 1_000_000) -> HistoricalBar:
    c = Decimal(str(close))
    return HistoricalBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=idx),
        open=c - Decimal("0.5"),
        high=c + Decimal("0.5"),
        low=c - Decimal("1.0"),
        close=c,
        volume=volume,
    )


def _closes(values: list[float]) -> list[Decimal]:
    return [Decimal(str(v)) for v in values]


def test_sma_returns_average_of_last_n_values():
    values = _closes([10, 12, 14, 16, 18])
    assert sma(values, 3) == Decimal("16.0000")
    assert sma(values, 6) is None


def test_ema_is_smoother_than_sma_on_trend():
    rising = _closes([float(i) for i in range(1, 30)])
    ema_value = ema(rising, 10)
    sma_value = sma(rising, 10)
    assert ema_value is not None and sma_value is not None
    # On a monotonic rise, EMA(short-period) leans toward recent values, so it
    # must be at least as high as the SMA over the same window.
    assert ema_value >= sma_value


def test_rsi_overbought_on_monotonic_rise():
    rising = _closes([100 + i * 0.5 for i in range(40)])
    value = rsi(rising)
    assert value is not None
    assert value >= 90


def test_rsi_oversold_on_monotonic_fall():
    falling = _closes([100 - i * 0.5 for i in range(40)])
    value = rsi(falling)
    assert value is not None
    assert value <= 10


def test_macd_returns_three_components_when_enough_history():
    closes = _closes([100 + (i % 5) - 2 for i in range(60)])
    m, sig, hist = macd(closes)
    assert m is not None
    assert sig is not None
    assert hist is not None


def test_bollinger_position_inside_zero_to_one():
    closes = _closes([100 + (i % 7) for i in range(30)])
    upper, lower, position = bollinger(closes)
    assert upper is not None and lower is not None
    assert upper > lower
    assert position is not None
    assert 0 <= position <= 1


def test_atr_grows_with_wider_ranges():
    tight = [_bar(i, 100 + (i % 2) * 0.1) for i in range(30)]
    wide = [
        HistoricalBar(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=1_000_000,
        )
        for i in range(30)
    ]
    tight_atr = atr(tight)
    wide_atr = atr(wide)
    assert tight_atr is not None and wide_atr is not None
    assert wide_atr > tight_atr


def test_vwap_weights_high_volume_bars():
    def _flat_bar(idx: int, price: float, volume: int) -> HistoricalBar:
        p = Decimal(str(price))
        return HistoricalBar(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=idx),
            open=p,
            high=p,
            low=p,
            close=p,
            volume=volume,
        )

    bars = [_flat_bar(i, 100, 10_000) for i in range(5)] + [
        _flat_bar(i, 200, 1_000_000) for i in range(5, 10)
    ]
    value = vwap(bars)
    assert value is not None
    # Heavy bars at 200 dominate, so VWAP must lean toward 200.
    assert value > Decimal("190")


def test_momentum_positive_on_rise_and_negative_on_fall():
    rising = _closes([100 + i for i in range(30)])
    falling = _closes([100 - i for i in range(30)])
    assert momentum(rising, 10) is not None
    assert momentum(rising, 10) > 0
    assert momentum(falling, 10) is not None
    assert momentum(falling, 10) < 0


def test_classify_trend_returns_known_labels():
    assert classify_trend(Decimal("110"), Decimal("100"), Decimal("115"), 0.8) == "up"
    assert classify_trend(Decimal("90"), Decimal("100"), Decimal("85"), 0.2) == "down"
    assert classify_trend(None, None, Decimal("100"), 0.5) == "range"
    assert classify_trend(None, None, None, None) == "unknown"


def test_compute_timeframe_features_reports_bar_count_and_last_close():
    bars = [_bar(i, 100 + i * 0.2) for i in range(40)]
    features = compute_timeframe_features("1d", bars)
    assert features.bar_count == 40
    assert features.last_close == bars[-1].close
    assert features.trend in {"up", "down", "range", "unknown"}


def test_compute_liquidity_reports_relative_volume():
    bars = [_bar(i, 100, volume=1_000_000) for i in range(20)]
    profile = compute_liquidity(bars, current_volume=2_000_000)
    assert profile is not None
    assert profile.average_daily_volume == 1_000_000
    assert profile.relative_volume == 2.0


def test_compute_market_context_with_mock_provider_produces_features():
    provider = MockBrokerProvider()

    async def _run():
        snapshot = await provider.get_market_snapshot("AAPL")
        bars_1d = await provider.get_historical_bars("AAPL", "1d", 100)
        bars_1h = await provider.get_historical_bars("AAPL", "1h", 60)
        return snapshot, bars_1d, bars_1h

    snapshot, bars_1d, bars_1h = asyncio.run(_run())
    context = compute_market_context(
        snapshot,
        {"1d": bars_1d, "1h": bars_1h},
    )
    assert context.symbol == "AAPL"
    assert context.primary_timeframe is not None
    assert context.primary_timeframe.bar_count == 100
    # to_prompt_dict should contain the symbol and at least one timeframe
    prompt = context.to_prompt_dict()
    assert prompt["symbol"] == "AAPL"
    assert "1d" in prompt["timeframes"]


def test_market_context_from_snapshot_is_degraded_but_valid():
    snapshot = MarketSnapshot(
        symbol="AAPL",
        asset_type="equity",
        price=Decimal("100"),
        timestamp=datetime.now(UTC),
        source="test",
    )
    from app.market_data.models import MarketContext

    context = MarketContext.from_snapshot(snapshot, notes=["no bars"])
    assert context.primary_timeframe is None
    assert "no bars" in context.notes
