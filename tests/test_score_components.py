"""
test_score_components.py — PRD section 10.1

Tests that individual score components compute correctly from Filing data.

PRD requirement:
    Given a Filing with resource_estimate_new=True, filing_score component = 30.

PHASE 0 STATUS: These tests FAIL because the scoring rubric function is not
yet implemented (Phase 3). They are intentionally failing as per PRD Session 1
deliverable: "pytest skeleton with 3 failing tests".

The tests define the expected interface for the scoring rubric:
    compute_filing_score(filing: FilingModel) -> int
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.models import FilingModel


# ---------------------------------------------------------------------------
# Helper — minimum valid FilingModel
# ---------------------------------------------------------------------------


def make_filing(**kwargs) -> FilingModel:
    """Construct a minimal valid FilingModel with overrides."""
    defaults = dict(
        run_id=str(uuid4()),
        ticker="MP",
        cik="0001801170",
        form_type="8-K",
        filed_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        accession_number="0001801170-24-000001",
        document_url="https://www.sec.gov/Archives/edgar/data/1801170/000180117024000001/mp-20240115.htm",
        summary="MP Materials announces new NdPr resource estimate at Mountain Pass.",
        source_url="https://www.sec.gov/Archives/edgar/data/1801170/000180117024000001/mp-20240115.htm",
    )
    defaults.update(kwargs)
    return FilingModel(**defaults)


# ---------------------------------------------------------------------------
# Tests — these FAIL until Phase 3 implements compute_filing_score
# ---------------------------------------------------------------------------


class TestFilingScoreComponents:
    """
    Filing score component tests.

    These tests are INTENTIONALLY FAILING in Phase 0.
    They will pass when compute_filing_score() is implemented in Phase 3.
    """

    def test_resource_estimate_new_scores_30(self):
        """
        PRD requirement: resource_estimate_new=True → filing_score = 30 (max).

        This is the highest-weight filing signal: a new NI 43-101 or SK-1300
        resource estimate indicates a significant project milestone.

        FAILS until Phase 3: compute_filing_score not yet implemented.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 3 deliverable",
        )
        from src.scoring import compute_filing_score  # noqa: F401

        filing = make_filing(resource_estimate_new=True)
        score = compute_filing_score(filing)
        assert score == 30, f"resource_estimate_new=True should score 30, got {score}"

    def test_no_signals_scores_zero(self):
        """
        A filing with no positive signals scores 0.

        FAILS until Phase 3: compute_filing_score not yet implemented.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 3 deliverable",
        )
        from src.scoring import compute_filing_score  # noqa: F401

        filing = make_filing(
            resource_estimate_new=False,
            resource_estimate_updated=False,
            permit_granted=False,
            jv_announced=False,
            production_update=False,
            financing_announced=False,
            negative_flag=False,
        )
        score = compute_filing_score(filing)
        assert score == 0, f"Empty filing should score 0, got {score}"

    def test_negative_flag_reduces_score(self):
        """
        A negative_flag filing should score below 0 (penalty applied).

        FAILS until Phase 3: compute_filing_score not yet implemented.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 3 deliverable",
        )
        from src.scoring import compute_filing_score  # noqa: F401

        filing = make_filing(negative_flag=True)
        score = compute_filing_score(filing)
        assert score < 0, f"negative_flag filing should score < 0, got {score}"

    def test_filing_score_caps_at_30(self):
        """
        Filing score cannot exceed 30 (the maximum weight for this component).

        FAILS until Phase 3: compute_filing_score not yet implemented.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 3 deliverable",
        )
        from src.scoring import compute_filing_score  # noqa: F401

        filing = make_filing(
            resource_estimate_new=True,
            resource_estimate_updated=True,
            permit_granted=True,
            jv_announced=True,
            production_update=True,
            financing_announced=True,
        )
        score = compute_filing_score(filing)
        assert score <= 30, f"Filing score must not exceed 30, got {score}"
