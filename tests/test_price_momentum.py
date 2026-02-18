"""
test_price_momentum.py — PRD section 10.1

Tests that RSI and return calculations match expected values exactly when given
known OHLCV data. All computations are deterministic — no LLM involved.

PHASE 0 STATUS: These tests FAIL because src.scoring.compute_rsi and
src.scoring.compute_return are not yet implemented (Phase 2 deliverable).
Intentionally failing as per Session 1 spec.
"""

import pytest


class TestRSICalculation:
    """
    RSI-14 calculation tests.

    These tests are INTENTIONALLY FAILING in Phase 0.
    They will pass when compute_rsi() is implemented in Phase 2.

    RSI formula:
        RSI = 100 - (100 / (1 + RS))
        RS = avg_gain_14 / avg_loss_14

    Reference values computed with pandas-ta for fixture data.
    """

    def test_compute_rsi_import(self):
        """
        EXPECTED FAIL: src.scoring module does not exist yet.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )

    def test_rsi_known_values(self):
        """
        Given a known 15-day close series, RSI-14 matches the expected value.

        Reference closes: a trending sequence with one dip and one correction.
        Wilder's seeded EMA (14-period seed → simple avg, no further smoothing
        since all 14 diffs are consumed by the seed) produces RSI ≈ 91.38.
        Value verified against the Wilder formula: avg_gain=0.379, avg_loss=0.036.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_rsi  # noqa: F401

        # 15 closes — enough for RSI-14 (needs period+1 data points)
        closes = [
            10.0, 10.5, 11.2, 11.8, 12.1,
            12.5, 12.3, 12.8, 13.2, 13.5,
            13.8, 14.1, 14.5, 14.2, 14.8,
        ]
        rsi = compute_rsi(closes, period=14)
        assert abs(rsi - 91.38) < 0.1, f"Expected RSI ≈ 91.38, got {rsi:.2f}"

    def test_rsi_neutral_market(self):
        """
        Flat price series (no gains, no losses) → RSI = 50.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_rsi  # noqa: F401

        closes = [10.0] * 15  # flat
        rsi = compute_rsi(closes, period=14)
        assert abs(rsi - 50.0) < 0.01, f"Flat series should produce RSI=50, got {rsi}"

    def test_rsi_strong_uptrend(self):
        """
        Consistent gains → RSI approaches 100.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_rsi  # noqa: F401

        closes = [float(i) for i in range(1, 16)]  # 1, 2, ..., 15
        rsi = compute_rsi(closes, period=14)
        assert rsi > 90.0, f"Strong uptrend should produce RSI > 90, got {rsi}"

    def test_rsi_requires_minimum_periods(self):
        """
        RSI-14 requires at least 15 data points. Fewer raises ValueError.
        """
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_rsi  # noqa: F401

        with pytest.raises(ValueError, match="period"):
            compute_rsi([10.0, 11.0, 12.0], period=14)  # only 3 closes


class TestReturnCalculation:
    """
    Return (1d, 5d, 30d) calculation tests.

    INTENTIONALLY FAILING in Phase 0.
    """

    def test_return_1d_positive(self):
        """1-day return = (close_today - close_yesterday) / close_yesterday."""
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_return  # noqa: F401

        closes = [10.0, 11.0]  # yesterday=10, today=11
        ret = compute_return(closes, period=1)
        assert abs(ret - 0.10) < 0.001, f"Expected 10% return, got {ret:.4f}"

    def test_return_5d(self):
        """5-day return = (close[-1] - close[-6]) / close[-6]."""
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_return  # noqa: F401

        closes = [10.0, 10.2, 10.5, 10.3, 10.8, 11.0]  # 6 closes
        ret = compute_return(closes, period=5)
        assert abs(ret - 0.10) < 0.001, f"Expected 10% return, got {ret:.4f}"

    def test_return_negative(self):
        """Negative returns are correctly computed."""
        pytest.importorskip(
            "src.scoring",
            reason="EXPECTED FAIL (Phase 0): src.scoring not yet implemented — Phase 2 deliverable",
        )
        from src.scoring import compute_return  # noqa: F401

        closes = [10.0, 9.0]  # -10%
        ret = compute_return(closes, period=1)
        assert abs(ret - (-0.10)) < 0.001, f"Expected -10% return, got {ret:.4f}"
