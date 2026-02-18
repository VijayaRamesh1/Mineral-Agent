"""
EDGAR EFTS client for the Critical Minerals Signal Hunter.

Wraps SEC's EDGAR full-text search (EFTS) and archives endpoints with:
  - Configurable rate limiting (default 10 req/s, per SEC fair-use policy)
  - Tenacity retry logic (3 attempts, exponential backoff)
  - Structured response parsing into dicts consumed by filing_scanner

Public API
----------
EdgarClient(rate_limit_rps)   — rate-limited httpx wrapper
query_efts(...)               — search EDGAR EFTS for filings
fetch_exhibit_text(...)       — download primary exhibit text for a filing
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint constants
# ---------------------------------------------------------------------------

EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


# ---------------------------------------------------------------------------
# EdgarClient — rate-limited HTTP wrapper
# ---------------------------------------------------------------------------


class EdgarClient:
    """
    HTTP client for EDGAR endpoints with token-bucket rate limiting.

    Parameters
    ----------
    rate_limit_rps : int
        Maximum requests per second. SEC fair-use policy is 10 req/s.
    """

    def __init__(self, rate_limit_rps: int = 10) -> None:
        self.rate_limit_rps = rate_limit_rps
        self._min_interval: float = 1.0 / rate_limit_rps
        self._last_call_at: float = 0.0

    def _throttle(self) -> None:
        """Block until the minimum inter-request interval has elapsed."""
        now = time.monotonic()
        wait = self._min_interval - (now - self._last_call_at)
        if wait > 0:
            time.sleep(wait)
        self._last_call_at = time.monotonic()

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited GET request."""
        self._throttle()
        return httpx.get(url, **kwargs)


# Module-level default client (shared by query_efts / fetch_exhibit_text)
_default_client = EdgarClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_hyphens(accession: str) -> str:
    """0001801170-24-000001 → 000180117024000001"""
    return accession.replace("-", "")


def _cik_int(cik: str) -> str:
    """Strip leading zeros: '0001801170' → '1801170'"""
    return str(int(cik))


# ---------------------------------------------------------------------------
# query_efts — EDGAR full-text search
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _efts_get(client: EdgarClient, params: dict[str, str]) -> dict[str, Any]:
    """Inner GET with tenacity retry. Raises on HTTP error after 3 attempts."""
    resp = client.get(EFTS_BASE, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def query_efts(
    ticker: str,
    cik: str | None,
    start_date: date,
    end_date: date,
    form_types: list[str],
    client: EdgarClient | None = None,
) -> list[dict[str, Any]]:
    """
    Query EDGAR EFTS for filings matching the given parameters.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol. Used as the search term when ``cik`` is None.
    cik : str | None
        SEC Central Index Key (with leading zeros). When provided it is used
        as the primary search term for more precise matching.
    start_date, end_date : date
        Inclusive date range (filed_date field).
    form_types : list[str]
        Filing form types to include, e.g. ``["8-K", "10-Q"]``.
    client : EdgarClient | None
        Optional override for testing. Defaults to the module-level client.

    Returns
    -------
    list[dict]
        Each dict contains:
          accession_number, form_type, filed_date, period_of_report,
          cik, document_url
        Returns ``[]`` on any network or parse failure.
    """
    _client = client or _default_client

    # Use CIK as primary search term for precision; fall back to ticker symbol
    query = f'"{cik}"' if cik else f'"{ticker}"'
    params: dict[str, str] = {
        "q": query,
        "dateRange": "custom",
        "startdt": start_date.isoformat(),
        "enddt": end_date.isoformat(),
        "forms": ",".join(form_types),
    }

    try:
        data = _efts_get(_client, params)
    except Exception as exc:
        logger.warning("EDGAR EFTS query failed for %s: %s", ticker, exc)
        return []

    hits = data.get("hits", {}).get("hits", [])
    results: list[dict[str, Any]] = []

    for hit in hits:
        src = hit.get("_source", {})
        accession = hit.get("_id", "")
        acc_clean = _strip_hyphens(accession)
        cik_val = cik or ""
        cik_int = _cik_int(cik_val) if cik_val else ""

        doc_url = (
            f"{ARCHIVES_BASE}/{cik_int}/{acc_clean}/"
            if cik_int
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type={','.join(form_types)}&dateb=&owner=include&count=10"
        )

        results.append(
            {
                "accession_number": accession,
                "form_type": src.get("form_type", ""),
                "filed_date": src.get("file_date", ""),
                "period_of_report": src.get("period_of_report"),
                "cik": cik_val,
                "document_url": doc_url,
            }
        )

    logger.info(
        "edgar.query_efts: ticker=%s found=%d", ticker, len(results)
    )
    return results


# ---------------------------------------------------------------------------
# fetch_exhibit_text — download primary filing document
# ---------------------------------------------------------------------------


def fetch_exhibit_text(
    cik: str,
    accession_number: str,
    client: EdgarClient | None = None,
    max_chars: int = 8000,
) -> str:
    """
    Fetch the primary exhibit text for a filing from EDGAR archives.

    Attempts to retrieve the filing index JSON, then downloads the first
    non-metadata document (typically the 8-K body or 10-Q/10-K section).

    Parameters
    ----------
    cik : str
        SEC CIK (with or without leading zeros).
    accession_number : str
        Accession number with hyphens, e.g. ``"0001801170-24-000001"``.
    client : EdgarClient | None
        Optional override for testing.
    max_chars : int
        Maximum characters to return from the document text.

    Returns
    -------
    str
        Exhibit text, truncated to ``max_chars``. Empty string on failure.
    """
    _client = client or _default_client
    acc_clean = _strip_hyphens(accession_number)
    cik_int = _cik_int(cik)

    index_url = f"{ARCHIVES_BASE}/{cik_int}/{acc_clean}/{acc_clean}-index.json"
    try:
        resp = _client.get(index_url, timeout=30.0)
        resp.raise_for_status()
        index = resp.json()
    except Exception as exc:
        logger.warning(
            "edgar.fetch_exhibit_text: index fetch failed %s/%s: %s",
            cik,
            accession_number,
            exc,
        )
        return ""

    documents = index.get("documents", [])
    if not documents:
        return ""

    # Prefer the primary filing document; skip XML/XBRL and exhibit indices
    skip_types = {"", "XML", "EX-99.2", "EX-101.INS", "EX-101.SCH"}
    primary = next(
        (d for d in documents if d.get("type", "") not in skip_types),
        documents[0],
    )
    doc_name = primary.get("name", "")
    if not doc_name:
        return ""

    doc_url = f"{ARCHIVES_BASE}/{cik_int}/{acc_clean}/{doc_name}"
    try:
        doc_resp = _client.get(doc_url, timeout=30.0)
        doc_resp.raise_for_status()
        return doc_resp.text[:max_chars]
    except Exception as exc:
        logger.warning(
            "edgar.fetch_exhibit_text: document fetch failed %s: %s", doc_url, exc
        )
        return ""
