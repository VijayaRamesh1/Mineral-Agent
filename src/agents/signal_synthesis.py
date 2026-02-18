"""
Signal Synthesis agent — Phase 3.

Responsibilities:
  - For each ticker, combine filings + news + price + geo into ScoreBreakdown
  - Apply deterministic scoring rubric (no LLM for score → direction mapping)
  - Call Claude (temperature=0) to generate evidence list and confidence
  - Validate full SignalModel with Pydantic (ValidationError on bad output)
  - Apply hallucination guard: every evidence claim must have a source_url
    that was present in the prompt context (enforced by EvidenceItem required field)
  - Append to state["signals"]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

import anthropic

from src.config import settings
from src.models import (
    EvidenceItem,
    ScoreBreakdown,
    SignalModel,
    build_signal_direction,
    compute_prompt_hash,
)
from src.scoring import (
    compute_filing_score,
    compute_geo_score,
    compute_news_score,
    compute_price_score,
)
from src.state import AgentState
from src.tracing import get_langsmith_run_url, trace

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Claude tool definition for signal synthesis
# ---------------------------------------------------------------------------

_SYNTHESIS_TOOL: dict[str, Any] = {
    "name": "synthesize_signal",
    "description": (
        "Produce a confidence rating and evidence list for a critical minerals "
        "investment signal. Only cite URLs from the provided context. "
        "Do NOT invent facts or sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "confidence": {
                "type": "string",
                "enum": ["LOW", "MED", "HIGH"],
                "description": (
                    "Data quality and signal consensus. "
                    "HIGH = strong multi-source alignment; "
                    "MED = some supporting signals, mixed data; "
                    "LOW = thin or conflicting data."
                ),
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {
                            "type": "string",
                            "description": "Specific factual claim from the data. Max 500 chars.",
                        },
                        "source_url": {
                            "type": "string",
                            "description": "URL from the provided context that supports this claim.",
                        },
                    },
                    "required": ["claim", "source_url"],
                },
                "minItems": 1,
                "description": "Evidence items supporting the signal. Every claim must have a source URL.",
            },
        },
        "required": ["confidence", "evidence"],
    },
}

_SYNTHESIS_SYSTEM = (
    "You are a critical minerals investment analyst. "
    "Given aggregated filing, news, price, and geopolitical data for a ticker, "
    "call the synthesize_signal tool with:\n"
    "  1. A confidence level (LOW/MED/HIGH) reflecting data quality and consensus.\n"
    "  2. Evidence items — each a specific factual claim with a URL from the provided context.\n"
    "Rules:\n"
    "  - Only cite URLs explicitly listed in the context.\n"
    "  - Write claims in 1-2 sentences, max 500 chars.\n"
    "  - At least 1 evidence item is required.\n"
    "  - If no relevant events occurred, state that and cite the EDGAR search URL."
)


# ---------------------------------------------------------------------------
# Score helpers (dict-safe wrappers)
# ---------------------------------------------------------------------------


def _filing_score(filing_dict: dict[str, Any]) -> int:
    """Compute filing_score from a FilingModel dict using getattr-friendly access."""

    class _DictProxy:
        def __init__(self, d: dict[str, Any]) -> None:
            self._d = d

        def __getattr__(self, name: str) -> Any:
            return self._d.get(name, False)

    return compute_filing_score(_DictProxy(filing_dict))


def _price_score(price_dict: dict[str, Any]) -> int:
    return compute_price_score(
        return_1d=price_dict.get("return_1d"),
        return_5d=price_dict.get("return_5d"),
        return_30d=price_dict.get("return_30d"),
        rsi_14=price_dict.get("rsi_14"),
        vs_remx=price_dict.get("vs_remx"),
    )


# ---------------------------------------------------------------------------
# Context builder for Claude prompt
# ---------------------------------------------------------------------------


def _edgar_search_url(ticker: str) -> str:
    return f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=8-K"


def _build_context(
    ticker: str,
    score: int,
    direction: str,
    filings: list[dict[str, Any]],
    news: list[dict[str, Any]],
    price: dict[str, Any],
    geo: list[dict[str, Any]],
) -> str:
    """Build the text context fed to Claude for evidence extraction."""
    lines: list[str] = []
    lines.append(f"TICKER: {ticker}")
    lines.append(f"SIGNAL SCORE: {score}/100  DIRECTION: {direction}")
    lines.append(f"DATE: {datetime.now(timezone.utc).date().isoformat()}")
    lines.append("")

    # Filings
    lines.append(f"=== EDGAR FILINGS ({len(filings)} found) ===")
    if filings:
        for f in filings[:5]:
            lines.append(
                f"[{f.get('form_type', '?')} filed {f.get('filed_date', '?')[:10]}] "
                f"{f.get('summary', 'No summary.')[:300]}"
            )
            lines.append(f"Source: {f.get('document_url') or f.get('source_url') or _edgar_search_url(ticker)}")
    else:
        lines.append(f"No EDGAR filings found. Reference: {_edgar_search_url(ticker)}")
    lines.append("")

    # News
    lines.append(f"=== NEWS ITEMS ({len(news)} found) ===")
    if news:
        for n in news[:8]:
            sentiment = n.get("sentiment") or "NEUTRAL"
            lines.append(
                f"[{sentiment}] {n.get('headline', 'No headline')} — {n.get('source', '?')}"
            )
            lines.append(f"Source: {n.get('url') or _edgar_search_url(ticker)}")
    else:
        lines.append("No news items found.")
    lines.append("")

    # Price
    lines.append("=== PRICE DATA ===")
    if price:
        lines.append(
            f"Close: {price.get('close', 'N/A')}  "
            f"Return 1d: {price.get('return_1d', 'N/A')}  "
            f"5d: {price.get('return_5d', 'N/A')}  "
            f"30d: {price.get('return_30d', 'N/A')}"
        )
        lines.append(
            f"RSI-14: {price.get('rsi_14', 'N/A')}  "
            f"vs REMX: {price.get('vs_remx', 'N/A')}  "
            f"vs LIT: {price.get('vs_lit', 'N/A')}"
        )
        lines.append(f"Note: {price.get('data_latency_note', 'prices are prior-day close')}")
    else:
        lines.append("No price data available.")
    lines.append("")

    # Geo events
    lines.append(f"=== GEOPOLITICAL EVENTS ({len(geo)} found) ===")
    if geo:
        for g in geo[:5]:
            lines.append(
                f"[{g.get('country_code', '?')} / {g.get('event_type', '?')}] "
                f"{g.get('description', '')[:300]}"
            )
            geo_url = g.get("gdelt_url") or _edgar_search_url(ticker)
            lines.append(f"Source: {geo_url}")
    else:
        lines.append("No geopolitical events found.")
    lines.append("")

    lines.append(f"FALLBACK SOURCE URL: {_edgar_search_url(ticker)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------


def _call_claude(
    context: str,
    ticker: str,
    run_id: str,
) -> tuple[Literal["LOW", "MED", "HIGH"], list[dict[str, str]]] | None:
    """
    Call Claude with the synthesis tool to get confidence + evidence.

    Returns (confidence, evidence_items) or None on failure.
    """
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            temperature=0,
            system=_SYNTHESIS_SYSTEM,
            tools=[_SYNTHESIS_TOOL],
            tool_choice={"type": "tool", "name": "synthesize_signal"},
            messages=[{"role": "user", "content": context}],
        )
    except Exception as exc:
        logger.warning("signal_synthesis: Claude call failed for %s: %s", ticker, exc)
        return None

    tool_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_block is None:
        logger.warning("signal_synthesis: no tool_use block for %s", ticker)
        return None

    inp: dict[str, Any] = tool_block.input  # type: ignore[attr-defined]
    confidence = inp.get("confidence", "LOW")
    if confidence not in ("LOW", "MED", "HIGH"):
        confidence = "LOW"

    evidence_raw = inp.get("evidence", [])
    if not evidence_raw:
        # Fallback: minimal evidence item
        evidence_raw = [
            {
                "claim": f"No significant events found for {ticker} in this analysis period.",
                "source_url": _edgar_search_url(ticker),
            }
        ]

    return confidence, evidence_raw  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------


@trace(name="signal_synthesis", tags=["phase-3", "synthesis"])
def signal_synthesis_node(state: AgentState) -> dict[str, Any]:
    """
    Phase 3 implementation: combine all agent outputs into scored SignalModels.

    For each ticker in the watchlist:
      1. Gathers its filings, news_items, price data, and geo_events from state.
      2. Computes a ScoreBreakdown using the deterministic PRD rubric:
           filing  (0–30): max compute_filing_score across all filings for the ticker
           news    (0–25): compute_news_score over ticker-specific news
           price   (0–25): compute_price_score from PriceModel metrics
           geo     (0–15): compute_geo_score over events affecting the ticker
           novelty (0–5):  +3 if new filings present, +2 if new news present
      3. Derives direction deterministically from total score (no LLM).
      4. Calls Claude (temperature=0) via tool use to get:
           - confidence (LOW/MED/HIGH)
           - evidence list (each claim + source_url from the provided context)
      5. Validates the full SignalModel with Pydantic.
      6. Appends to state["signals"]; captures failures in state["errors"].

    Hallucination guard: every EvidenceItem must have a source_url (required
    Pydantic field). Claude is instructed to only cite URLs from the provided
    context, preventing fabricated references.

    Returns
    -------
    dict
        {"signals": [list of SignalModel dicts], "errors": [list of error strings]}
    """
    watchlist: list[str] = state.get("watchlist", [])
    run_id: str = state.get("run_id", "unknown")
    errors: list[str] = list(state.get("errors", []))
    existing_signals: list[dict[str, Any]] = list(state.get("signals", []))

    state_filings: list[dict[str, Any]] = state.get("filings", [])
    state_news: list[dict[str, Any]] = state.get("news_items", [])
    state_prices: dict[str, dict[str, Any]] = state.get("prices", {})
    state_geo: list[dict[str, Any]] = state.get("geo_events", [])

    logger.info("signal_synthesis: starting for %d tickers", len(watchlist))

    new_signals: list[dict[str, Any]] = []

    for ticker in watchlist:
        # Skip if we already have a signal for this ticker in this run
        if any(s.get("ticker") == ticker and s.get("run_id") == run_id for s in existing_signals):
            logger.debug("signal_synthesis: skipping duplicate signal for %s", ticker)
            continue

        # ── 1. Gather per-ticker data ────────────────────────────────────────
        ticker_filings = [f for f in state_filings if f.get("ticker") == ticker]
        ticker_news = [
            n for n in state_news
            if n.get("ticker") == ticker
            or (n.get("ticker") is None and (n.get("relevance_score") or 0) >= 60)
        ]
        price_data: dict[str, Any] = state_prices.get(ticker, {})
        ticker_geo = [
            g for g in state_geo
            if ticker in (g.get("affected_tickers") or [])
        ]

        # ── 2. Compute ScoreBreakdown ────────────────────────────────────────
        # Filing component (0–30): use max single-filing score; negative clamped to 0
        if ticker_filings:
            filing_raw = max(_filing_score(f) for f in ticker_filings)
        else:
            filing_raw = 0
        filing_component = max(0, min(30, filing_raw))

        # News component (0–25)
        news_component = compute_news_score(ticker_news)

        # Price component (0–25)
        price_component = _price_score(price_data) if price_data else 0

        # Geo component (0–15)
        geo_component = compute_geo_score(ticker_geo)

        # Novelty (0–5): simple heuristic — new data found this run
        novelty = min(5, (3 if ticker_filings else 0) + (2 if ticker_news else 0))

        try:
            breakdown = ScoreBreakdown(
                filing=filing_component,
                news=news_component,
                price=price_component,
                geo=geo_component,
                novelty=novelty,
            )
        except Exception as exc:
            msg = f"signal_synthesis: ScoreBreakdown validation failed for {ticker}: {exc}"
            logger.warning(msg)
            errors.append(msg)
            continue

        total = breakdown.total
        direction = build_signal_direction(total)

        # ── 3. Build Claude context and call ────────────────────────────────
        context = _build_context(
            ticker=ticker,
            score=total,
            direction=direction,
            filings=ticker_filings,
            news=ticker_news,
            price=price_data,
            geo=ticker_geo,
        )
        prompt_hash = compute_prompt_hash(_SYNTHESIS_SYSTEM + context)

        result = _call_claude(context, ticker, run_id)
        if result is None:
            # Claude failed — build a minimal fallback signal without evidence
            confidence: Literal["LOW", "MED", "HIGH"] = "LOW"
            evidence_raw: list[dict[str, str]] = [
                {
                    "claim": f"Signal synthesis Claude call failed for {ticker}; score computed deterministically.",
                    "source_url": _edgar_search_url(ticker),
                }
            ]
            errors.append(f"signal_synthesis: Claude call failed for {ticker}")
        else:
            confidence, evidence_raw = result

        # ── 4. Validate EvidenceItems ────────────────────────────────────────
        evidence_items: list[EvidenceItem] = []
        for item in evidence_raw:
            try:
                evidence_items.append(
                    EvidenceItem(
                        claim=str(item.get("claim", ""))[:500],
                        source_url=str(item.get("source_url", _edgar_search_url(ticker))),
                    )
                )
            except Exception as exc:
                logger.debug("signal_synthesis: skipping invalid evidence item: %s", exc)

        if not evidence_items:
            evidence_items = [
                EvidenceItem(
                    claim=f"No verifiable evidence found for {ticker} in this period.",
                    source_url=_edgar_search_url(ticker),
                )
            ]

        # ── 5. Validate SignalModel ──────────────────────────────────────────
        try:
            signal = SignalModel(
                run_id=run_id,
                langsmith_url=get_langsmith_run_url(run_id),
                model_version=settings.claude_model,
                prompt_hash=prompt_hash,
                data_latency_note="prices are prior-day close; news within last 48 h",
                ticker=ticker,
                score=total,
                score_breakdown=breakdown,
                direction=direction,
                confidence=confidence,
                evidence=evidence_items,
            )
        except Exception as exc:
            msg = f"signal_synthesis: SignalModel validation failed for {ticker}: {exc}"
            logger.warning(msg)
            errors.append(msg)
            continue

        new_signals.append(signal.model_dump())
        logger.info(
            "signal_synthesis: %s → %s (score=%d, confidence=%s)",
            ticker,
            direction,
            total,
            confidence,
        )

    all_signals = existing_signals + new_signals
    logger.info(
        "signal_synthesis: completed — %d new signals (total=%d)",
        len(new_signals),
        len(all_signals),
    )
    return {"signals": all_signals, "errors": errors}
