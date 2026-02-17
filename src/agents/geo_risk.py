"""
Geo Risk agent — Phase 2.

Responsibilities:
  - Query GDELT API for geopolitical events related to critical minerals
    producing countries (China, DRC, Russia, Kazakhstan, Australia, Canada)
  - Call Claude with a rubric to score supply chain risk severity (0–100)
  - Produce GeoEvent Pydantic models
  - Append to state["geo_events"]

Phase 0: stub implementation.
"""

from __future__ import annotations

import logging
from typing import Any

from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)

GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Countries with significant critical minerals production or processing
HIGH_RISK_COUNTRIES = [
    "CN",  # China — dominant REE processing
    "CD",  # DRC — cobalt
    "RU",  # Russia — nickel, palladium
    "KZ",  # Kazakhstan — uranium
    "AU",  # Australia — lithium, rare earths
    "CA",  # Canada — uranium, nickel
]


@trace(name="geo_risk", tags=["phase-2", "geo"])
def geo_risk_node(state: AgentState) -> dict[str, Any]:
    """
    STUB — Phase 2 implementation pending (Session 3).

    Will:
      1. Query GDELT API for recent events (last 48 hours) mentioning
         critical minerals + high-risk countries.
      2. Call Claude with a rubric to score each event's supply chain
         risk severity (0–100).
      3. Map events to affected tickers from state["watchlist"].
      4. Return {"geo_events": [list of GeoEvent dicts]}.
    """
    logger.info("geo_risk: STUB — skipping GDELT query (Phase 2 not yet implemented)")
    return {"geo_events": []}
