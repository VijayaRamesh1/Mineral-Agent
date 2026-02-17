"""
One-shot pipeline runner.

Usage:
    python run_pipeline.py
    python run_pipeline.py --tickers MP UUUU NB

This script is the cron-triggered entry point and the Docker 'pipeline'
service command. It invokes the LangGraph pipeline_graph synchronously
and exits with code 0 on success, 1 on failure.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid

from src.config import settings
from src.graph import pipeline_graph
from src.state import initial_state

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main(tickers: list[str] | None = None) -> int:
    run_id = str(uuid.uuid4())
    logger.info("Starting pipeline run: run_id=%s", run_id)

    state = initial_state(run_id=run_id, watchlist=tickers or [])
    try:
        result = pipeline_graph.invoke(state)
        signal_count = len(result.get("signals", []))
        error_count = len(result.get("errors", []))
        logger.info(
            "Pipeline complete: run_id=%s signals=%d errors=%d",
            run_id, signal_count, error_count,
        )
        if result.get("errors"):
            for err in result["errors"]:
                logger.warning("Pipeline error: %s", err)
        return 0
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Critical Minerals Signal Hunter")
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=None,
        help="Ticker symbols to process (default: load from watchlist.yaml)",
    )
    args = parser.parse_args()
    sys.exit(main(args.tickers))
