"""
FastAPI wrapper for the Critical Minerals Signal Hunter pipeline.

Endpoints:
  GET  /health         — liveness check
  POST /run            — trigger a full pipeline run (background thread)
  GET  /signals        — query recent signals from SQLite
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from src.config import settings
from src.db import query_signals
from src.graph import pipeline_graph
from src.state import initial_state

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Critical Minerals Signal Hunter",
    description="Multi-agent pipeline for critical minerals investment signals.",
    version="1.0.0",
)

# Thread pool for running the synchronous LangGraph pipeline without
# blocking the FastAPI event loop.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline-worker")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    watchlist: list[str] | None = None  # None = load from watchlist.yaml


class RunResponse(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    ticker_count: int
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_watchlist_tickers() -> list[str]:
    """Load ticker symbols from watchlist.yaml."""
    try:
        path = Path(str(settings.watchlist_path))
        with path.open() as f:
            data = yaml.safe_load(f)
        return [entry["ticker"] for entry in data.get("tickers", [])]
    except Exception as exc:
        logger.error("Failed to load watchlist: %s", exc)
        return []


def _run_pipeline_sync(run_id: str, watchlist: list[str]) -> None:
    """Execute the LangGraph pipeline synchronously (called from thread pool)."""
    try:
        state = initial_state(run_id=run_id, watchlist=watchlist)
        result = pipeline_graph.invoke(state)
        signal_count = len(result.get("signals", []))
        error_count = len(result.get("errors", []))
        logger.info(
            "Pipeline complete: run_id=%s signals=%d errors=%d",
            run_id,
            signal_count,
            error_count,
        )
    except Exception as exc:
        logger.exception(
            "Background pipeline run failed: run_id=%s error=%s", run_id, exc
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check — returns 200 if API is running."""
    return {"status": "ok", "service": "critical-minerals-agent"}


@app.post("/run", response_model=RunResponse)
async def trigger_run(request: RunRequest | None = None) -> RunResponse:
    """
    Trigger a full pipeline run.

    Accepts immediately and executes the LangGraph pipeline in a background
    thread pool so the event loop is not blocked. Returns the run_id for
    tracking progress via GET /signals.
    """
    run_id = str(uuid.uuid4())
    watchlist = (request.watchlist if request else None) or _load_watchlist_tickers()

    logger.info("API /run: triggered run_id=%s tickers=%d", run_id, len(watchlist))

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_pipeline_sync, run_id, watchlist)

    return RunResponse(
        run_id=run_id,
        status="accepted",
        started_at=datetime.utcnow(),
        ticker_count=len(watchlist),
        message=f"Pipeline run accepted for {len(watchlist)} tickers.",
    )


@app.get("/signals")
async def get_signals(
    ticker: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Query recent signals from SQLite.

    Parameters
    ----------
    ticker : str, optional
        Filter to a specific ticker symbol (e.g. ``MP``, ``UUUU``).
    limit : int
        Maximum number of signals to return (default 50).
    """
    try:
        signals = query_signals(ticker=ticker, limit=limit)
        return {"signals": signals, "count": len(signals)}
    except Exception as exc:
        logger.error("API /signals: query failed: %s", exc)
        return {"signals": [], "count": 0, "error": str(exc)}
