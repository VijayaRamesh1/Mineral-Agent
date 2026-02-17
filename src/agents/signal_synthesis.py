"""
Signal Synthesis agent — Phase 3.

Responsibilities:
  - For each ticker, combine filings + news + price + geo into ScoreBreakdown
  - Apply deterministic scoring rubric (no LLM for score → direction mapping)
  - Call Claude (temperature=0) to generate evidence list and confidence
  - Validate full SignalModel with Pydantic (ValidationError on bad output)
  - Apply hallucination guard: every evidence claim must have a source_url
  - Append to state["signals"]

Phase 0: stub implementation.
"""

from __future__ import annotations

import logging
from typing import Any

from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)


@trace(name="signal_synthesis", tags=["phase-3", "synthesis"])
def signal_synthesis_node(state: AgentState) -> dict[str, Any]:
    """
    STUB — Phase 3 implementation pending (Session 4).

    Will:
      1. For each ticker in state["watchlist"]:
         a. Gather relevant filings, news_items, price, geo_events.
         b. Compute ScoreBreakdown using deterministic rubric:
            - filing score: resource_estimate_new=+30, permit=+20, etc.
            - news score: positive_sentiment_count * weight
            - price score: RSI + relative momentum formula
            - geo score: max(geo_risk_score for affected events)
            - novelty score: delta vs last signal in SQLite
         c. Derive direction from score (deterministic — no LLM).
         d. Call Claude (temperature=0) for: evidence list, confidence.
         e. Validate with SignalModel Pydantic model.
         f. Attach LangSmith trace URL.
      2. Return {"signals": [list of SignalModel dicts]}.

    Hallucination guard:
      Every EvidenceItem.claim must reference content present in the source
      documents (checked via Pydantic validator + embedding similarity ≥ 0.85).
    """
    logger.info(
        "signal_synthesis: STUB — skipping %d tickers (Phase 3 not yet implemented)",
        len(state.get("watchlist", [])),
    )
    return {"signals": []}
