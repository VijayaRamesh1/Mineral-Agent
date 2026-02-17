"""
LangGraph state schema for the Critical Minerals Signal Hunter pipeline.

The AgentState TypedDict is the single shared state object passed between
all nodes in the StateGraph. Every agent reads from and writes to this state.
"""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    Shared pipeline state. All fields are optional at initialization except
    run_id and watchlist, which are set by the orchestrator on startup.

    Fields
    ------
    run_id : str
        UUID for this pipeline run. Links all signals to a single LangSmith
        trace and SQLite run record.
    watchlist : list[str]
        Ticker symbols to process in this run. Loaded from watchlist.yaml.
    filings : list[dict]
        Raw FilingModel dicts produced by the filing_scanner agent.
        Each entry corresponds to one EDGAR filing (8-K, 10-Q, etc.).
    news_items : list[dict]
        Raw NewsItem dicts produced by the news_sentiment agent.
        Sourced from RSS feeds (Mining.com, Kitco, Stockhouse) and GDELT.
    prices : dict[str, dict]
        Ticker → PriceModel dict produced by the price_tracker agent.
        Keys are ticker symbols; values contain OHLCV and computed metrics.
    geo_events : list[dict]
        GeoEvent dicts produced by the geo_risk agent.
        Sourced from GDELT; scored by Claude rubric.
    signals : list[dict]
        SignalModel dicts produced by the signal_synthesis agent.
        One signal per ticker. The final output of the pipeline.
    errors : list[str]
        Accumulated error messages from any agent. Partial failures are
        captured here so the pipeline continues with remaining tickers.
    report_md : str
        Markdown report produced by the report_writer agent.
        Rendered from Jinja2 template — no LLM involved in formatting.
    """

    run_id: str
    watchlist: list[str]
    filings: list[dict[str, Any]]
    news_items: list[dict[str, Any]]
    prices: dict[str, dict[str, Any]]
    geo_events: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    errors: list[str]
    report_md: str


def initial_state(run_id: str, watchlist: list[str]) -> AgentState:
    """Return a fresh AgentState for the start of a pipeline run."""
    return AgentState(
        run_id=run_id,
        watchlist=watchlist,
        filings=[],
        news_items=[],
        prices={},
        geo_events=[],
        signals=[],
        errors=[],
        report_md="",
    )
