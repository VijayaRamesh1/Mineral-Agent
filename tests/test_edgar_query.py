"""
test_edgar_query.py — PRD section 10.1

Tests EDGAR EFTS query using mocked HTTP responses.

PRD requirement:
    EDGAR EFTS mock returns known filings for MP for a fixed date range.

PHASE 0 STATUS: These tests FAIL because the edgar_query module is not yet
implemented (Phase 1 deliverable). Intentionally failing as per Session 1 spec.
"""

import pytest
from datetime import date


# Fixture: a real EDGAR EFTS response for MP Materials (CIK: 0001801170)
# Retrieved 2024-01-15 for the date range 2024-01-01 to 2024-01-15.
# This is stored as a fixture so tests run offline.
MOCK_EFTS_RESPONSE = {
    "hits": {
        "hits": [
            {
                "_id": "0001801170-24-000001",
                "_source": {
                    "period_of_report": "2024-01-12",
                    "file_date": "2024-01-15",
                    "form_type": "8-K",
                    "entity_name": "MP Materials Corp.",
                    "file_num": "000-00000",
                    "period": "20240112",
                },
            }
        ],
        "total": {"value": 1},
    }
}


class TestEdgarQuery:
    """
    EDGAR EFTS query tests.
    These tests FAIL until Phase 1 implements src.edgar.query_efts.
    """

    def test_edgar_query_import(self):
        """
        EXPECTED FAIL: src.edgar module does not exist yet.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )

    def test_query_efts_returns_known_filing_for_mp(self):
        """
        Mock EDGAR EFTS returns the known 8-K for MP for 2024-01-01 to 2024-01-15.

        FAILS until Phase 1: query_efts not yet implemented.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )
        from src.edgar import query_efts  # noqa: F401

        # Will use respx to mock httpx in Phase 1
        results = query_efts(
            ticker="MP",
            cik="0001801170",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 15),
            form_types=["8-K"],
        )
        assert len(results) == 1
        assert results[0]["accession_number"] == "0001801170-24-000001"
        assert results[0]["form_type"] == "8-K"

    def test_edgar_respects_rate_limit(self):
        """
        EDGAR queries must not exceed 10 requests/second.

        FAILS until Phase 1: rate limiter not yet implemented.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )
        from src.edgar import EdgarClient  # noqa: F401

        client = EdgarClient(rate_limit_rps=10)
        assert client.rate_limit_rps == 10

    def test_edgar_returns_empty_for_no_filings(self):
        """
        Query for a ticker with no filings in range returns empty list.

        FAILS until Phase 1: query_efts not yet implemented.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )
        from src.edgar import query_efts  # noqa: F401

        results = query_efts(
            ticker="GIGA",
            cik=None,
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 2),
            form_types=["8-K"],
        )
        assert results == []
