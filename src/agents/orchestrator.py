"""
Orchestrator node — pipeline entry point.

Responsibilities:
  - Validates and loads watchlist from watchlist.yaml
  - Sets run_id in state
  - Fans out to ticker-level agents via LangGraph Send API (Phase 1+)
  - Collects results and routes to report_writer

Phase 0: stub that loads watchlist and sets run_id.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

import yaml

from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)


@trace(name="orchestrator", tags=["orchestrator"])
def orchestrator_node(state: AgentState) -> dict[str, Any]:
    """
    Entry point for the pipeline.

    Loads the watchlist (if not already set in state) and initialises run_id.
    In Phase 1+ this will fan out to filing_scanner, price_tracker, etc.
    via LangGraph's Send API for parallel ticker-level processing.
    """
    updates: dict[str, Any] = {}

    # Assign run_id if not already set
    if not state.get("run_id"):
        updates["run_id"] = str(uuid.uuid4())
        logger.info("Orchestrator: new run_id=%s", updates["run_id"])
    else:
        logger.info("Orchestrator: resuming run_id=%s", state["run_id"])

    # Load watchlist if not already populated
    if not state.get("watchlist"):
        watchlist_path = Path(os.getenv("WATCHLIST_PATH", "watchlist.yaml"))
        try:
            with watchlist_path.open() as f:
                data = yaml.safe_load(f)
            tickers = [entry["ticker"] for entry in data.get("tickers", [])]
            updates["watchlist"] = tickers
            logger.info("Orchestrator: loaded %d tickers from %s", len(tickers), watchlist_path)
        except Exception as exc:
            error_msg = f"orchestrator: failed to load watchlist from {watchlist_path}: {exc}"
            logger.error(error_msg)
            updates["errors"] = state.get("errors", []) + [error_msg]

    return updates
