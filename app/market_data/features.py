"""Deterministic feature engineering over historical bars.

All math runs in pure Python / Decimal so the module has no numpy/pandas
dependency and produces stable outputs for replay and tests.
"""

from __future__ import annotations

import math
from decimal import Decimal
from statistics import fmean, pstdev

from app.market_data.models import (
    HistoricalBar,
    LiquidityProfile,
    MarketContext,
    MarketSnapshot,
    TimeframeFeatures,
)


PRICE_QUANTIZE = Decimal("0.0001")


def _q(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(PRICE_QUANTIZE)


def sma(values: list[Decimal], period: int) -> Decimal | None:
    if len(values) < period or period <= 0:
        return None
    window = values[-period:]
    return _q(sum(window) / Decimal(period))


def ema_series(values: list[Decimal], period: int) -> list[Decimal]:
    if not values or period <= 0:
        return []
    k = Decimal(2) / Decimal(period + 1)
    result: list[Decimal] = []
    prev: Decimal | None = None
    for value in values:
        if prev is None:
            prev = value
        else:
            prev = (value - prev) * k + prev
        result.append(prev)
    return result


def ema(values: list[Decimal], period: int) -> Decimal | None:
    if len(values) < period:
        return None
    series = ema_series(values, period)
    return _q(series[-1]) if series else None


def rsi(closes: list[Decimal], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = float(closes[i] - closes[i - 1])
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(
    closes: list[Decimal], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if len(closes) < slow + signal:
        return None, None, None
    fast_series = ema_series(closes, fast)
    slow_series = ema_series(closes, slow)
    macd_series = [f - s for f, s in zip(fast_series, slow_series, strict=False)]
    signal_series = ema_series(macd_series, signal)
    macd_last = macd_series[-1]
    signal_last = signal_series[-1]
    hist = macd_last - signal_last
    return _q(macd_last), _q(signal_last), _q(hist)


def bollinger(
    closes: list[Decimal], period: int = 20, k: float = 2.0
) -> tuple[Decimal | None, Decimal | None, float | None]:
    if len(closes) < period:
        return None, None, None
    window = [float(c) for c in closes[-period:]]
    mean = fmean(window)
    std = pstdev(window) if len(window) > 1 else 0.0
    upper = mean + k * std
    lower = mean - k * std
    last = float(closes[-1])
    band_width = upper - lower
    position = (last - lower) / band_width if band_width > 0 else 0.5
    position = max(0.0, min(1.0, position))
    return _q(upper), _q(lower), round(position, 3)


def atr(bars: list[HistoricalBar], period: int = 14) -> Decimal | None:
    if len(bars) <= period:
        return None
    trs: list[Decimal] = []
    prev_close = bars[0].close
    for bar in bars[1:]:
        tr = max(
            bar.high - bar.low,
            abs(bar.high - prev_close),
            abs(bar.low - prev_close),
        )
        trs.append(tr)
        prev_close = bar.close
    if len(trs) < period:
        return None
    window = trs[-period:]
    return _q(sum(window) / Decimal(period))


def vwap(bars: list[HistoricalBar]) -> Decimal | None:
    if not bars:
        return None
    numer = Decimal(0)
    denom = Decimal(0)
    for bar in bars:
        if bar.volume is None or bar.volume <= 0:
            continue
        typical = (bar.high + bar.low + bar.close) / Decimal(3)
        numer += typical * Decimal(bar.volume)
        denom += Decimal(bar.volume)
    if denom == 0:
        return None
    return _q(numer / denom)


def momentum(closes: list[Decimal], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    base = closes[-(lookback + 1)]
    if base <= 0:
        return None
    return round(float((closes[-1] - base) / base), 6)


def realized_volatility(closes: list[Decimal], lookback: int = 20) -> float | None:
    if len(closes) <= lookback:
        return None
    rets: list[float] = []
    for i in range(len(closes) - lookback, len(closes)):
        prev = closes[i - 1]
        if prev <= 0:
            continue
        rets.append(float((closes[i] - prev) / prev))
    if len(rets) < 2:
        return None
    return round(pstdev(rets), 6)


def classify_trend(
    sma_short: Decimal | None,
    sma_long: Decimal | None,
    last_close: Decimal | None,
    band_position: float | None,
) -> str:
    if last_close is None:
        return "unknown"
    if sma_short is not None and sma_long is not None:
        if last_close > sma_short > sma_long:
            return "up"
        if last_close < sma_short < sma_long:
            return "down"
    if band_position is not None:
        if band_position >= 0.7:
            return "up"
        if band_position <= 0.3:
            return "down"
    return "range"


def compute_timeframe_features(interval: str, bars: list[HistoricalBar]) -> TimeframeFeatures:
    closes = [bar.close for bar in bars]
    if not closes:
        return TimeframeFeatures(interval=interval, bar_count=0)

    sma_short = sma(closes, 20)
    sma_long = sma(closes, 50)
    ema_fast = ema(closes, 12)
    ema_slow = ema(closes, 26)
    macd_v, macd_sig, macd_hist = macd(closes)
    bb_upper, bb_lower, bb_pos = bollinger(closes)
    atr_v = atr(bars)
    vwap_v = vwap(bars)
    mom_5 = momentum(closes, 5)
    mom_20 = momentum(closes, 20)
    rsi_v = rsi(closes)
    rv = realized_volatility(closes)

    trend = classify_trend(sma_short, sma_long, closes[-1], bb_pos)

    return TimeframeFeatures(
        interval=interval,
        bar_count=len(bars),
        last_close=closes[-1],
        sma_short=sma_short,
        sma_long=sma_long,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi_14=rsi_v,
        macd=macd_v,
        macd_signal=macd_sig,
        macd_histogram=macd_hist,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        bb_position=bb_pos,
        atr_14=atr_v,
        vwap=vwap_v,
        momentum_5=mom_5,
        momentum_20=mom_20,
        realized_volatility=rv,
        trend=trend,  # type: ignore[arg-type]
    )


def compute_liquidity(
    bars: list[HistoricalBar], current_volume: int | None
) -> LiquidityProfile | None:
    if not bars:
        return None
    volumes = [bar.volume or 0 for bar in bars]
    if not any(volumes):
        return None
    adv = int(round(fmean(volumes)))
    dollar_volumes = [
        float(bar.close) * (bar.volume or 0) for bar in bars if bar.volume
    ]
    avg_dollar = Decimal(str(round(fmean(dollar_volumes), 2))) if dollar_volumes else None
    rel_vol = (current_volume / adv) if (current_volume and adv > 0) else None
    return LiquidityProfile(
        average_daily_volume=adv,
        average_dollar_volume=avg_dollar,
        relative_volume=round(rel_vol, 3) if rel_vol is not None else None,
    )


def compute_relative_strength(
    symbol_closes: list[Decimal], benchmark_closes: dict[str, list[Decimal]], lookback: int = 20
) -> dict[str, float]:
    rs: dict[str, float] = {}
    sym_mom = momentum(symbol_closes, lookback)
    if sym_mom is None:
        return rs
    for bench, closes in benchmark_closes.items():
        bench_mom = momentum(closes, lookback)
        if bench_mom is None:
            continue
        rs[bench] = round(sym_mom - bench_mom, 6)
    return rs


def compute_market_context(
    snapshot: MarketSnapshot,
    bars_by_interval: dict[str, list[HistoricalBar]],
    *,
    benchmark_bars: dict[str, list[HistoricalBar]] | None = None,
    notes: list[str] | None = None,
) -> MarketContext:
    timeframes: dict[str, TimeframeFeatures] = {}
    for interval, bars in bars_by_interval.items():
        timeframes[interval] = compute_timeframe_features(interval, bars)

    daily_bars = bars_by_interval.get("1d") or next(iter(bars_by_interval.values()), [])
    liquidity = compute_liquidity(daily_bars, snapshot.volume)

    rs: dict[str, float] = {}
    if benchmark_bars:
        symbol_daily = [bar.close for bar in daily_bars]
        bench_closes = {name: [b.close for b in bars] for name, bars in benchmark_bars.items() if bars}
        rs = compute_relative_strength(symbol_daily, bench_closes)

    return MarketContext(
        snapshot=snapshot,
        timeframes=timeframes,
        liquidity=liquidity,
        relative_strength=rs,
        notes=notes or [],
    )
