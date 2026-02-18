"""
Price Tracker agent — Phase 2.

Responsibilities:
  - Fetch OHLCV data for each ticker via yfinance
  - Fetch REMX and LIT ETF data as sector proxies
  - Compute deterministic metrics: 1d/5d/30d returns, RSI-14, relative return
  - Produce PriceModel Pydantic models
  - Append to state["prices"]

All computations are deterministic (no LLM). Unit tested with known fixtures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from src.models import PriceModel
from src.scoring import compute_price_score, compute_return, compute_rsi
from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)

PROXY_TICKERS = ["REMX", "LIT"]  # Sector proxies fetched for all runs

DATA_LATENCY_NOTE = "prices are prior-day close; 15-min delayed for real-time feeds"

# Days to download — enough for RSI-14 (needs 15+ closes) and 30d return
_DOWNLOAD_DAYS = "45d"


def _fetch_closes(ticker: str) -> list[float]:
    """
    Download recent closing prices for a single ticker via yfinance.

    Returns an empty list on any download failure (error logged, not raised).
    """
    try:
        data = yf.download(ticker, period=_DOWNLOAD_DAYS, progress=False, auto_adjust=True)
        if data.empty:
            logger.warning("price_tracker: no data returned for %s", ticker)
            return []
        closes = data["Close"].dropna().tolist()
        # yfinance may return a DataFrame with MultiIndex columns
        if isinstance(closes[0], (list, tuple)):
            closes = [c[0] for c in closes]
        return [float(c) for c in closes]
    except Exception as exc:  # noqa: BLE001
        logger.warning("price_tracker: download failed for %s: %s", ticker, exc)
        return []


def _build_price_model(
    ticker: str,
    run_id: str,
    closes: list[float],
    remx_closes: list[float],
    lit_closes: list[float],
) -> PriceModel | None:
    """
    Build a PriceModel from raw close series.

    Returns None if there is insufficient data to compute any metric.
    """
    if len(closes) < 2:
        logger.warning("price_tracker: insufficient closes for %s (%d)", ticker, len(closes))
        return None

    # Use the most recent yfinance row for OHLCV
    # yfinance auto_adjust=True gives adjusted close in "Close" column
    try:
        raw = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
        if raw.empty:
            return None
        last_row = raw.iloc[-1]
        open_ = float(last_row["Open"])
        high = float(last_row["High"])
        low = float(last_row["Low"])
        close = float(last_row["Close"])
        volume = int(last_row["Volume"])
        as_of = last_row.name
        if hasattr(as_of, "to_pydatetime"):
            as_of_dt = as_of.to_pydatetime().replace(tzinfo=None)
        else:
            as_of_dt = datetime.utcnow()
    except Exception as exc:  # noqa: BLE001
        logger.warning("price_tracker: OHLCV fetch failed for %s: %s", ticker, exc)
        return None

    # Computed metrics — each is None if there are insufficient closes
    return_1d = compute_return(closes, 1) if len(closes) >= 2 else None
    return_5d = compute_return(closes, 5) if len(closes) >= 6 else None
    return_30d = compute_return(closes, 30) if len(closes) >= 31 else None
    rsi_14 = compute_rsi(closes, 14) if len(closes) >= 15 else None

    # Relative returns vs proxy ETFs over the same window as return_5d
    vs_remx: float | None = None
    vs_lit: float | None = None
    if return_5d is not None and len(remx_closes) >= 6:
        remx_ret = compute_return(remx_closes, 5)
        vs_remx = return_5d - remx_ret
    if return_5d is not None and len(lit_closes) >= 6:
        lit_ret = compute_return(lit_closes, 5)
        vs_lit = return_5d - lit_ret

    price_score = compute_price_score(return_1d, return_5d, return_30d, rsi_14, vs_remx)

    return PriceModel(
        ticker=ticker,
        run_id=run_id,
        as_of_date=as_of_dt,
        data_latency_note=DATA_LATENCY_NOTE,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        return_1d=return_1d,
        return_5d=return_5d,
        return_30d=return_30d,
        rsi_14=rsi_14,
        vs_remx=vs_remx,
        vs_lit=vs_lit,
        price_score=price_score,
    )


@trace(name="price_tracker", tags=["phase-2", "price"])
def price_tracker_node(state: AgentState) -> dict[str, Any]:
    """
    Phase 2 implementation: fetch OHLCV + compute metrics for all tickers.

    Fetches proxy ETFs (REMX, LIT) once, then processes each watchlist ticker.
    Failures per-ticker are logged and recorded in state["errors"]; the pipeline
    continues with the remaining tickers.

    Returns
    -------
    dict
        {"prices": {ticker: PriceModel.model_dump(), ...}}
    """
    watchlist: list[str] = state.get("watchlist", [])
    run_id: str = state.get("run_id", "unknown")
    errors: list[str] = list(state.get("errors", []))

    logger.info("price_tracker: fetching prices for %d tickers", len(watchlist))

    # Fetch proxy ETFs once
    remx_closes = _fetch_closes("REMX")
    lit_closes = _fetch_closes("LIT")
    logger.info(
        "price_tracker: proxy closes — REMX=%d LIT=%d",
        len(remx_closes),
        len(lit_closes),
    )

    prices: dict[str, Any] = {}

    for ticker in watchlist:
        closes = _fetch_closes(ticker)
        model = _build_price_model(ticker, run_id, closes, remx_closes, lit_closes)
        if model is None:
            msg = f"price_tracker: could not build PriceModel for {ticker}"
            logger.warning(msg)
            errors.append(msg)
        else:
            prices[ticker] = model.model_dump()
            logger.info(
                "price_tracker: %s close=%.4f rsi=%.1f score=%d",
                ticker,
                model.close,
                model.rsi_14 or 0.0,
                model.price_score or 0,
            )

    logger.info("price_tracker: completed %d/%d tickers", len(prices), len(watchlist))
    return {"prices": prices, "errors": errors}
