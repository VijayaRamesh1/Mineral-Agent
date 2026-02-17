"""
Filing Scanner agent — Phase 1.

Responsibilities:
  - Query EDGAR EFTS (full-text search) for recent 8-K filings
  - Download exhibit text for each filing
  - Call Claude (claude-sonnet-4-6) with structured output to extract FilingModel
  - Validate output with Pydantic; append to state["filings"]

Phase 0: stub implementation. Returns empty list with a log message.
Implemented in Session 2.
"""

from __future__ import annotations

import logging
from typing import Any

from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)

# EDGAR EFTS endpoint (no API key required; rate limit: 10 req/s)
EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&forms=8-K"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"


@trace(name="filing_scanner", tags=["phase-1", "edgar"])
def filing_scanner_node(state: AgentState) -> dict[str, Any]:
    """
    STUB — Phase 1 implementation pending (Session 2).

    Will:
      1. For each ticker in state["watchlist"], query EDGAR EFTS for
         recent 8-K filings (last 48 hours).
      2. Download exhibit text (Item 7.01, Item 8.01).
      3. Call Claude with structured output → FilingModel.
      4. Validate with Pydantic.
      5. Return {"filings": [list of FilingModel dicts]}.

    Rate limiting: 10 req/s max against EDGAR endpoints.
    """
    logger.info(
        "filing_scanner: STUB — skipping %d tickers (Phase 1 not yet implemented)",
        len(state.get("watchlist", [])),
    )
    return {"filings": []}
