"""
FastAPI wrapper for the Critical Minerals Signal Hunter pipeline.

Endpoints:
  GET  /health         — liveness check
  POST /run            — trigger a pipeline run manually
  GET  /signals        — query recent signals from SQLite (Phase 4)

Phase 0: /health and /run stubs only.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.state import initial_state

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Critical Minerals Signal Hunter",
    description="Multi-agent pipeline for critical minerals investment signals.",
    version="0.1.0",
)


class RunRequest(BaseModel):
    watchlist: list[str] | None = None  # None = load from watchlist.yaml


class RunResponse(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    ticker_count: int
    message: str


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check — returns 200 if API is running."""
    return {"status": "ok", "service": "critical-minerals-agent"}


@app.post("/run", response_model=RunResponse)
async def trigger_run(request: RunRequest | None = None) -> RunResponse:
    """
    Trigger a full pipeline run.

    Phase 0: validates request and returns a stub response.
    Phase 5: executes pipeline_graph.invoke() in a background task.
    """
    run_id = str(uuid.uuid4())
    watchlist = (request.watchlist if request else None) or []

    logger.info("API /run: triggered run_id=%s tickers=%s", run_id, watchlist or "from yaml")

    # Phase 0 stub: return accepted response without running pipeline
    # Phase 5: asyncio.create_task(run_pipeline_async(run_id, watchlist))
    return RunResponse(
        run_id=run_id,
        status="accepted",
        started_at=datetime.utcnow(),
        ticker_count=len(watchlist),
        message="Pipeline run accepted. Phase 0 stub — pipeline execution not yet wired.",
    )


@app.get("/signals")
async def get_signals(
    ticker: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Query recent signals from SQLite.

    Phase 0: stub — returns empty list.
    Phase 4: queries SQLite signals table with optional ticker filter.
    """
    return {
        "signals": [],
        "count": 0,
        "message": "Phase 4 stub — SQLite persistence not yet implemented.",
    }
