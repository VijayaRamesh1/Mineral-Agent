"""
Deterministic scoring functions for the Critical Minerals Signal Hunter.

All functions are pure / side-effect-free and unit-tested with known fixtures.
No LLM is involved in any computation here.

Functions
---------
compute_rsi(closes, period)
    RSI-14 via Wilder's seeded exponential smoothing.
compute_return(closes, period)
    Simple period return: (close[-1] - close[-(period+1)]) / close[-(period+1)].
compute_filing_score(filing)
    Map FilingModel boolean signals to a -10 to 30 integer component score.
compute_price_score(...)
    Map PriceModel metrics to a 0–25 integer component score.
compute_news_score(news_items)
    Map news sentiment items to a 0–25 integer component score.
compute_geo_score(geo_events)
    Map geopolitical risk events to a 0–15 integer component score.
"""

from __future__ import annotations

from typing import Any, Sequence


def _v(obj: Any, key: str, default: Any = None) -> Any:
    """Get a value from either a dict or an object attribute."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def compute_rsi(closes: Sequence[float], period: int = 14) -> float:
    """
    Compute RSI using Wilder's seeded exponential smoothing.

    Parameters
    ----------
    closes : sequence of float
        Closing prices in chronological order (oldest first).
        Must contain at least ``period + 1`` values.
    period : int
        Lookback period. Default 14.

    Returns
    -------
    float
        RSI value in the range [0, 100].

    Raises
    ------
    ValueError
        If ``len(closes) < period + 1``.
    """
    if len(closes) < period + 1:
        raise ValueError(
            f"compute_rsi requires at least period+1={period + 1} closes, "
            f"got {len(closes)}"
        )

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # Seed: simple average of the first `period` changes
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing for all subsequent periods
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def compute_return(closes: Sequence[float], period: int = 1) -> float:
    """
    Compute the simple price return over ``period`` trading days.

    Parameters
    ----------
    closes : sequence of float
        Closing prices in chronological order (oldest first).
        Must contain at least ``period + 1`` values.
    period : int
        Number of trading days. Default 1 (day-over-day return).

    Returns
    -------
    float
        Fractional return, e.g. 0.05 means +5%.

    Raises
    ------
    ValueError
        If ``len(closes) < period + 1``.
    ZeroDivisionError
        If the base close price is zero.
    """
    if len(closes) < period + 1:
        raise ValueError(
            f"compute_return requires at least period+1={period + 1} closes, "
            f"got {len(closes)}"
        )

    base = closes[-(period + 1)]
    current = closes[-1]
    return (current - base) / base


def compute_filing_score(filing: Any) -> int:
    """
    Map FilingModel boolean signals to a -10 to 30 integer component score.

    Scoring rubric (from PRD section 7.3):
      resource_estimate_new    → +30 (max; highest-weight event)
      resource_estimate_updated → +15
      permit_granted           → +10
      jv_announced             → +10
      production_update        → +8
      financing_announced      → +8
      negative_flag            → -10 (penalty)

    Capped to the range [-10, 30].
    """
    score = 0

    if getattr(filing, "resource_estimate_new", False):
        score += 30
    if getattr(filing, "resource_estimate_updated", False):
        score += 15
    if getattr(filing, "permit_granted", False):
        score += 10
    if getattr(filing, "jv_announced", False):
        score += 10
    if getattr(filing, "production_update", False):
        score += 8
    if getattr(filing, "financing_announced", False):
        score += 8
    if getattr(filing, "negative_flag", False):
        score -= 10

    return max(-10, min(30, score))


def compute_price_score(
    return_1d: float | None,
    return_5d: float | None,
    return_30d: float | None,
    rsi_14: float | None,
    vs_remx: float | None,
) -> int:
    """
    Map price metrics to a 0–25 integer component score.

    Scoring rubric (additive, capped at 25):
      - Momentum (return_5d):  > +5% → +8, > +2% → +5, > 0% → +2
      - RSI signal:            < 35 (oversold) → +6, > 70 (overbought) → -3
      - 30d trend (return_30d): > +10% → +5, > +3% → +3
      - Relative strength (vs_remx): > +3% → +6, > 0% → +3
    """
    score = 0

    if return_5d is not None:
        if return_5d > 0.05:
            score += 8
        elif return_5d > 0.02:
            score += 5
        elif return_5d > 0.0:
            score += 2

    if rsi_14 is not None:
        if rsi_14 < 35:
            score += 6
        elif rsi_14 > 70:
            score -= 3

    if return_30d is not None:
        if return_30d > 0.10:
            score += 5
        elif return_30d > 0.03:
            score += 3

    if vs_remx is not None:
        if vs_remx > 0.03:
            score += 6
        elif vs_remx > 0.0:
            score += 3

    return max(0, min(25, score))


def compute_news_score(news_items: Sequence[Any]) -> int:
    """
    Map news sentiment items to a 0–25 integer component score.

    Accepts a sequence of NewsItem objects or equivalent dicts.

    Scoring rubric (additive, capped at 25):
      - POSITIVE with relevance >= 70: +5
      - POSITIVE with relevance >= 40: +3
      - POSITIVE with any relevance:   +1
      - NEGATIVE item:                 -3
      - NEUTRAL item:                  +0
    """
    score = 0
    for item in news_items:
        sentiment = _v(item, "sentiment")
        relevance = _v(item, "relevance_score", 0) or 0
        if sentiment == "POSITIVE":
            if relevance >= 70:
                score += 5
            elif relevance >= 40:
                score += 3
            else:
                score += 1
        elif sentiment == "NEGATIVE":
            score -= 3
    return max(0, min(25, score))


def compute_geo_score(geo_events: Sequence[Any]) -> int:
    """
    Map geopolitical risk events to a 0–15 integer component score.

    Accepts a sequence of GeoEvent objects or equivalent dicts.

    Uses the maximum geo_risk_score (0–100) across all provided events,
    scaled proportionally to the 0–15 component range.

    Parameters
    ----------
    geo_events : sequence
        GeoEvent models or dicts with a ``geo_risk_score`` field.

    Returns
    -------
    int
        0–15 component score.
    """
    if not geo_events:
        return 0
    max_risk = max((_v(e, "geo_risk_score", 0) or 0 for e in geo_events), default=0)
    return max(0, min(15, round(max_risk * 0.15)))
