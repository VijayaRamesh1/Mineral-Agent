"""
test_signal_direction.py — PRD section 10.1

Tests that the deterministic score → direction mapping is correct.
No LLM involved. These tests verify the scoring rubric thresholds.

PRD requirement:
    score=65 → BULL
    score=45 → WATCH
    score=35 → BEAR

PHASE 0 STATUS: These tests PASS immediately (the mapping is implemented).
They serve as regression guards for the core scoring logic.
"""

import pytest

from src.models import build_signal_direction


class TestSignalDirection:
    """Deterministic score → direction mapping tests."""

    # --- PRD-specified cases ---

    def test_score_65_is_bull(self):
        """PRD: score=65 → BULL."""
        assert build_signal_direction(65) == "BULL"

    def test_score_45_is_watch(self):
        """PRD: score=45 → WATCH."""
        assert build_signal_direction(45) == "WATCH"

    def test_score_35_is_bear(self):
        """PRD: score=35 → BEAR."""
        assert build_signal_direction(35) == "BEAR"

    # --- Boundary conditions ---

    def test_score_60_is_bull(self):
        """Lower boundary of BULL: score=60 → BULL."""
        assert build_signal_direction(60) == "BULL"

    def test_score_59_is_watch(self):
        """Upper boundary of WATCH: score=59 → WATCH."""
        assert build_signal_direction(59) == "WATCH"

    def test_score_40_is_watch(self):
        """Lower boundary of WATCH: score=40 → WATCH."""
        assert build_signal_direction(40) == "WATCH"

    def test_score_39_is_bear(self):
        """Upper boundary of BEAR: score=39 → BEAR."""
        assert build_signal_direction(39) == "BEAR"

    def test_score_100_is_bull(self):
        """Maximum score → BULL."""
        assert build_signal_direction(100) == "BULL"

    def test_score_0_is_bear(self):
        """Minimum score → BEAR."""
        assert build_signal_direction(0) == "BEAR"

    # --- Range coverage ---

    @pytest.mark.parametrize("score", range(60, 101))
    def test_all_bull_scores(self, score: int):
        """Every score in [60, 100] maps to BULL."""
        assert build_signal_direction(score) == "BULL"

    @pytest.mark.parametrize("score", range(40, 60))
    def test_all_watch_scores(self, score: int):
        """Every score in [40, 59] maps to WATCH."""
        assert build_signal_direction(score) == "WATCH"

    @pytest.mark.parametrize("score", range(0, 40))
    def test_all_bear_scores(self, score: int):
        """Every score in [0, 39] maps to BEAR."""
        assert build_signal_direction(score) == "BEAR"
