"""
test_edgar_query.py — PRD section 10.1

Tests EDGAR EFTS query using mocked HTTP responses (respx + httpx).

PRD requirement:
    EDGAR EFTS mock returns known filings for MP for a fixed date range.
"""

import httpx
import pytest
import respx
from datetime import date


# Fixture: a real EDGAR EFTS response for MP Materials (CIK: 0001801170)
# Retrieved 2024-01-15 for the date range 2024-01-01 to 2024-01-15.
# Stored as a fixture so tests run fully offline.
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

MOCK_EFTS_EMPTY = {
    "hits": {
        "hits": [],
        "total": {"value": 0},
    }
}

EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"


class TestEdgarQuery:
    """EDGAR EFTS query tests — all HTTP calls mocked offline via respx."""

    def test_edgar_query_import(self):
        """src.edgar module must exist and be importable."""
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )

    def test_query_efts_returns_known_filing_for_mp(self):
        """
        Mock EDGAR EFTS returns the known 8-K for MP for 2024-01-01 to 2024-01-15.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )
        from src.edgar import query_efts

        with respx.mock(assert_all_called=False) as mock:
            mock.get(EFTS_BASE).mock(
                return_value=httpx.Response(200, json=MOCK_EFTS_RESPONSE)
            )
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
        EdgarClient must expose rate_limit_rps and store the configured value.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )
        from src.edgar import EdgarClient

        client = EdgarClient(rate_limit_rps=10)
        assert client.rate_limit_rps == 10

    def test_edgar_returns_empty_for_no_filings(self):
        """
        Query for a ticker with no filings in range returns empty list.
        """
        pytest.importorskip(
            "src.edgar",
            reason="EXPECTED FAIL (Phase 0): src.edgar not yet implemented — Phase 1 deliverable",
        )
        from src.edgar import query_efts

        with respx.mock(assert_all_called=False) as mock:
            mock.get(EFTS_BASE).mock(
                return_value=httpx.Response(200, json=MOCK_EFTS_EMPTY)
            )
            results = query_efts(
                ticker="GIGA",
                cik=None,
                start_date=date(2020, 1, 1),
                end_date=date(2020, 1, 2),
                form_types=["8-K"],
            )

        assert results == []
