"""
Filing Scanner agent — Phase 1.

Responsibilities:
  - Query EDGAR EFTS (full-text search) for recent 8-K/10-Q/10-K filings
  - Download exhibit text for each filing via EDGAR archives
  - Call Gemini with function calling to extract FilingModel fields
  - Validate output with Pydantic; append to state["filings"]

Rate limiting: 10 req/s max against all EDGAR endpoints (SEC fair-use policy).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import google.generativeai as genai

from src.config import settings
from src.edgar import EdgarClient, fetch_exhibit_text, query_efts
from src.models import FilingModel, compute_prompt_hash
from src.state import AgentState
from src.tracing import trace

logger = logging.getLogger(__name__)

# EDGAR EFTS endpoint (no API key required; rate limit: 10 req/s)
EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&forms=8-K"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"


# ---------------------------------------------------------------------------
# Gemini function calling tool definition
# ---------------------------------------------------------------------------

_EXTRACTION_TOOLS: list[dict[str, Any]] = [
    {
        "function_declarations": [
            {
                "name": "extract_filing_signals",
                "description": (
                    "Extract structured investment signals from an EDGAR filing document. "
                    "Only mark a boolean True when the filing explicitly describes that event. "
                    "Do not infer or guess."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": (
                                "2-3 sentence summary of the filing's key announcements. "
                                "Max 2000 characters. Focus on material events only."
                            ),
                        },
                        "resource_estimate_new": {
                            "type": "boolean",
                            "description": "True only if the filing announces a NEW NI 43-101 or SK-1300 mineral resource estimate.",
                        },
                        "resource_estimate_updated": {
                            "type": "boolean",
                            "description": "True only if the filing updates an EXISTING resource estimate.",
                        },
                        "permit_granted": {
                            "type": "boolean",
                            "description": "True only if a regulatory permit or license was approved.",
                        },
                        "jv_announced": {
                            "type": "boolean",
                            "description": "True only if a joint venture or strategic partnership was announced.",
                        },
                        "production_update": {
                            "type": "boolean",
                            "description": "True only if the filing contains an operational or production milestone update.",
                        },
                        "financing_announced": {
                            "type": "boolean",
                            "description": "True only if an equity raise, debt financing, or offtake agreement was announced.",
                        },
                        "negative_flag": {
                            "type": "boolean",
                            "description": "True only if the filing describes an adverse event: suspension, regulatory fine, impairment writedown, or enforcement action.",
                        },
                        "key_entities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of key companies, agencies, or named projects mentioned.",
                        },
                    },
                    "required": [
                        "summary",
                        "resource_estimate_new",
                        "resource_estimate_updated",
                        "permit_granted",
                        "jv_announced",
                        "production_update",
                        "financing_announced",
                        "negative_flag",
                        "key_entities",
                    ],
                },
            }
        ]
    }
]

_SYSTEM_PROMPT = (
    "You are a mining and critical minerals analyst. "
    "Read the provided EDGAR filing excerpt and call the extract_filing_signals tool "
    "with the correct values. Be conservative: only mark a flag True when explicitly stated."
)


# ---------------------------------------------------------------------------
# Gemini extraction
# ---------------------------------------------------------------------------


def _load_cik_map() -> dict[str, str | None]:
    """
    Return ticker→CIK mapping loaded from watchlist.yaml.

    Tickers without edgar_cik map to None; the EDGAR search falls back
    to the ticker symbol in that case.
    """
    try:
        import yaml  # type: ignore[import-untyped]

        with open(settings.watchlist_path) as f:
            data = yaml.safe_load(f)
        return {t["ticker"]: t.get("edgar_cik") for t in data.get("tickers", [])}
    except Exception as exc:
        logger.warning("filing_scanner: could not load CIK map: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Watchlist CIK loader
# ---------------------------------------------------------------------------


def _extract_signals(
    text: str,
    ticker: str,
    run_id: str,
    filing_meta: dict[str, Any],
) -> FilingModel | None:
    """
    Call Gemini with function calling to extract FilingModel signals from exhibit text.

    Returns None if Gemini fails or output fails Pydantic validation.
    """
    if not text.strip():
        logger.warning("filing_scanner: empty exhibit text for %s", ticker)
        return None

    prompt = (
        f"Ticker: {ticker}\n"
        f"Form type: {filing_meta.get('form_type', 'unknown')}\n"
        f"Filed: {filing_meta.get('filed_date', 'unknown')}\n\n"
        f"--- FILING EXCERPT ---\n{text}\n--- END EXCERPT ---"
    )

    try:
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=_SYSTEM_PROMPT,
            tools=_EXTRACTION_TOOLS,
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=settings.gemini_temperature,
                max_output_tokens=settings.gemini_max_tokens,
            ),
            tool_config={
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": ["extract_filing_signals"],
                }
            },
        )
    except Exception as exc:
        logger.warning(
            "filing_scanner: Gemini call failed for %s/%s: %s",
            ticker,
            filing_meta.get("accession_number", ""),
            exc,
        )
        return None

    # Extract function_call from response
    try:
        part = response.candidates[0].content.parts[0]
        function_call = part.function_call
    except (IndexError, AttributeError):
        function_call = None

    if function_call is None or not hasattr(function_call, "args"):
        logger.warning(
            "filing_scanner: no function_call in Gemini response for %s", ticker
        )
        return None

    signals: dict[str, Any] = dict(function_call.args)

    # Parse filed_date
    try:
        filed_dt = datetime.fromisoformat(
            filing_meta.get("filed_date") or datetime.utcnow().date().isoformat()
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        filed_dt = datetime.now(timezone.utc)

    # Parse period_of_report (optional)
    period_raw = filing_meta.get("period_of_report")
    period_dt: datetime | None = None
    if period_raw:
        try:
            period_dt = datetime.fromisoformat(str(period_raw)).replace(tzinfo=timezone.utc)
        except ValueError:
            period_dt = None

    try:
        model = FilingModel(
            run_id=run_id,
            ticker=ticker,
            cik=filing_meta.get("cik") or None,
            form_type=filing_meta.get("form_type", "8-K"),
            filed_date=filed_dt,
            period_of_report=period_dt,
            accession_number=filing_meta.get("accession_number", ""),
            document_url=filing_meta.get("document_url", ""),
            source_url=filing_meta.get("document_url", ""),
            summary=str(signals.get("summary", ""))[:2000],
            resource_estimate_new=bool(signals.get("resource_estimate_new", False)),
            resource_estimate_updated=bool(signals.get("resource_estimate_updated", False)),
            permit_granted=bool(signals.get("permit_granted", False)),
            jv_announced=bool(signals.get("jv_announced", False)),
            production_update=bool(signals.get("production_update", False)),
            financing_announced=bool(signals.get("financing_announced", False)),
            negative_flag=bool(signals.get("negative_flag", False)),
            key_entities=list(signals.get("key_entities", [])),
        )
    except Exception as exc:
        logger.warning(
            "filing_scanner: FilingModel validation failed for %s: %s", ticker, exc
        )
        return None

    logger.info(
        "filing_scanner: %s %s extracted — resource_new=%s negative=%s",
        ticker,
        filing_meta.get("accession_number", ""),
        model.resource_estimate_new,
        model.negative_flag,
    )
    return model


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------


@trace(name="filing_scanner", tags=["phase-1", "edgar"])
def filing_scanner_node(state: AgentState) -> dict[str, Any]:
    """
    Phase 1 implementation: query EDGAR, extract signals via Gemini.

    For each watchlist ticker:
      1. Looks up its EDGAR CIK from watchlist.yaml (None for foreign/OTC).
      2. Queries EDGAR EFTS for 8-K/10-Q/10-K filings in the last 48 hours.
      3. Downloads the primary exhibit text (requires CIK for archive URL).
      4. Calls Gemini to extract FilingModel boolean signals via function calling.
      5. Validates with Pydantic and appends to state["filings"].

    Tickers without EDGAR coverage are attempted with a ticker-symbol search;
    exhibit download is skipped if no CIK is available. Per-ticker failures
    are captured in state["errors"] so the pipeline continues.

    Returns
    -------
    dict
        {"filings": [list of FilingModel dicts], "errors": [list of error strings]}
    """
    watchlist: list[str] = state.get("watchlist", [])
    run_id: str = state.get("run_id", "unknown")
    errors: list[str] = list(state.get("errors", []))
    existing_filings: list[dict[str, Any]] = list(state.get("filings", []))

    logger.info("filing_scanner: starting for %d tickers", len(watchlist))

    cik_map = _load_cik_map()
    edgar_client = EdgarClient(rate_limit_rps=settings.edgar_rate_limit_rps)

    # Date range: last news_lookback_hours (default 48 h)
    now_utc = datetime.now(timezone.utc)
    lookback = timedelta(hours=settings.news_lookback_hours)
    start_dt = (now_utc - lookback).date()
    end_dt = now_utc.date()

    new_filings: list[dict[str, Any]] = []

    for ticker in watchlist:
        cik = cik_map.get(ticker)

        # Query EDGAR EFTS (CIK-based or ticker-based)
        hits = query_efts(
            ticker=ticker,
            cik=cik,
            start_date=start_dt,
            end_date=end_dt,
            form_types=["8-K", "10-Q", "10-K"],
            client=edgar_client,
        )

        if not hits:
            logger.info("filing_scanner: no recent filings for %s", ticker)
            continue

        # Process up to max_filings_per_ticker
        for meta in hits[: settings.max_filings_per_ticker]:
            accession = meta.get("accession_number", "")

            # Skip duplicates already in state
            if any(f.get("accession_number") == accession for f in existing_filings):
                logger.debug("filing_scanner: skipping duplicate %s", accession)
                continue

            # Download exhibit text (requires CIK for archive URL construction)
            if not cik:
                logger.info(
                    "filing_scanner: no CIK for %s — skipping exhibit download", ticker
                )
                continue

            text = fetch_exhibit_text(
                cik=cik,
                accession_number=accession,
                client=edgar_client,
            )
            if not text:
                logger.info(
                    "filing_scanner: empty exhibit for %s/%s — skipping Gemini call",
                    ticker,
                    accession,
                )
                continue

            # Extract signals via Gemini function calling
            model = _extract_signals(text, ticker, run_id, meta)
            if model is None:
                msg = f"filing_scanner: extraction failed for {ticker}/{accession}"
                errors.append(msg)
                continue

            new_filings.append(model.model_dump())

    all_filings = existing_filings + new_filings
    logger.info(
        "filing_scanner: completed — %d new filings extracted (total=%d)",
        len(new_filings),
        len(all_filings),
    )
    return {"filings": all_filings, "errors": errors}
