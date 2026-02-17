"""
Price Tracker agent — Phase 2.

Responsibilities:
  - Fetch OHLCV data for each ticker via yfinance (pinned: 0.2.38)
  - Fetch REMX and LIT ETF data as sector proxies
  - Compute deterministic metrics: 1d/5d/30d returns, RSI-14, relative return
  - Produce PriceModel Pydantic models
  - Append to state["prices"]

All computations are deterministic (no LLM). Unit tested with known fixtures.

Phase 0: stub implementation.
"""

from __future__ import annotations

import logging
from typing import Any

from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)

PROXY_TICKERS = ["REMX", "LIT"]  # Sector proxies fetched for all runs


@trace(name="price_tracker", tags=["phase-2", "price"])
def price_tracker_node(state: AgentState) -> dict[str, Any]:
    """
    STUB — Phase 2 implementation pending (Session 3).

    Will:
      1. Call yfinance.download() for all tickers + REMX + LIT.
         Uses exponential backoff on failure (max 3 retries).
      2. Compute: return_1d, return_5d, return_30d, rsi_14, vs_remx, vs_lit.
      3. Validate with PriceModel Pydantic model.
      4. Return {"prices": {ticker: PriceModel.model_dump(), ...}}.

    Note: data_latency_note is REQUIRED in PriceModel. Will always be set to:
    "prices are prior-day close; 15-min delayed for real-time feeds"
    """
    logger.info(
        "price_tracker: STUB — skipping %d tickers (Phase 2 not yet implemented)",
        len(state.get("watchlist", [])),
    )
    return {"prices": {}}
