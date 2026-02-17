"""
News Sentiment agent — Phase 2 (partial) / Phase 3.

Responsibilities:
  - Parse RSS feeds from Mining.com, Kitco, Stockhouse via feedparser
  - Score each article for relevance and sentiment using Claude
  - Produce NewsItem Pydantic models
  - Append to state["news_items"]

Phase 0: stub implementation.
"""

from __future__ import annotations

import logging
from typing import Any

from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://www.mining.com/feed/",
    "https://www.kitco.com/rss/",
    # Stockhouse requires scraping — deferred to Phase 2
]


@trace(name="news_sentiment", tags=["phase-2", "news"])
def news_sentiment_node(state: AgentState) -> dict[str, Any]:
    """
    STUB — Phase 2 implementation pending (Session 3).

    Will:
      1. Fetch RSS feeds from Mining.com, Kitco, Stockhouse.
      2. Filter articles mentioning tickers in state["watchlist"].
      3. Call Claude to score sentiment (POSITIVE/NEUTRAL/NEGATIVE) and
         relevance (0–100) for each article.
      4. Return {"news_items": [list of NewsItem dicts]}.
    """
    logger.info(
        "news_sentiment: STUB — skipping news fetch (Phase 2 not yet implemented)",
    )
    return {"news_items": []}
