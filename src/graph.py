"""
LangGraph StateGraph definition for the Critical Minerals Signal Hunter.

DAG topology (Phase 0 stubs — all nodes run sequentially):

    orchestrator
         |
    filing_scanner
         |
    news_sentiment ─── price_tracker ─── geo_risk   (parallel in Phase 1+)
         |                   |               |
         └───────────────────┴───────────────┘
                             |
                    signal_synthesis
                             |
                      report_writer
                             |
                       memory_agent
                             |
                           END

Phase 1+ will use LangGraph's Send API to fan out filing_scanner,
price_tracker, and geo_risk across individual tickers in parallel.

Usage
-----
    from src.graph import build_graph

    app = build_graph()
    result = app.invoke(initial_state(run_id="...", watchlist=["MP", "UUUU"]))
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from src.agents.filing_scanner import filing_scanner_node
from src.agents.geo_risk import geo_risk_node
from src.agents.news_sentiment import news_sentiment_node
from src.agents.orchestrator import orchestrator_node
from src.agents.price_tracker import price_tracker_node
from src.agents.report_writer import memory_agent_node, report_writer_node
from src.agents.signal_synthesis import signal_synthesis_node
from src.state import AgentState

logger = logging.getLogger(__name__)

# Node name constants (avoids typos in edge definitions)
ORCHESTRATOR = "orchestrator"
FILING_SCANNER = "filing_scanner"
NEWS_SENTIMENT = "news_sentiment"
PRICE_TRACKER = "price_tracker"
GEO_RISK = "geo_risk"
SIGNAL_SYNTHESIS = "signal_synthesis"
REPORT_WRITER = "report_writer"
MEMORY_AGENT = "memory_agent"


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph.

    Returns a compiled graph ready for .invoke() or .stream().

    Phase 0: linear DAG. Phase 1+ will add parallel fan-out via Send API.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node(ORCHESTRATOR, orchestrator_node)
    graph.add_node(FILING_SCANNER, filing_scanner_node)
    graph.add_node(NEWS_SENTIMENT, news_sentiment_node)
    graph.add_node(PRICE_TRACKER, price_tracker_node)
    graph.add_node(GEO_RISK, geo_risk_node)
    graph.add_node(SIGNAL_SYNTHESIS, signal_synthesis_node)
    graph.add_node(REPORT_WRITER, report_writer_node)
    graph.add_node(MEMORY_AGENT, memory_agent_node)

    # Entry point
    graph.set_entry_point(ORCHESTRATOR)

    # Edges — linear for Phase 0
    # Phase 1+: news_sentiment, price_tracker, geo_risk run in parallel
    graph.add_edge(ORCHESTRATOR, FILING_SCANNER)
    graph.add_edge(FILING_SCANNER, NEWS_SENTIMENT)
    graph.add_edge(NEWS_SENTIMENT, PRICE_TRACKER)
    graph.add_edge(PRICE_TRACKER, GEO_RISK)
    graph.add_edge(GEO_RISK, SIGNAL_SYNTHESIS)
    graph.add_edge(SIGNAL_SYNTHESIS, REPORT_WRITER)
    graph.add_edge(REPORT_WRITER, MEMORY_AGENT)
    graph.add_edge(MEMORY_AGENT, END)

    logger.info("LangGraph: compiled pipeline DAG with %d nodes", 8)
    return graph.compile()


# Module-level singleton — import and use directly in run_pipeline.py
pipeline_graph = build_graph()
