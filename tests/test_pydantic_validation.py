"""
test_pydantic_validation.py — PRD section 10.1

Tests that invalid LLM output raises ValidationError rather than silently
propagating bad data. This is the core "hallucination guard" at the model level.

PRD requirement:
    Invalid LLM output (missing required field) raises ValidationError,
    not silent failure.

PHASE 0 STATUS: These tests PASS immediately (Pydantic validation works
out of the box). They serve as regression guards and documentation.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from src.models import (
    EvidenceItem,
    FilingModel,
    PriceModel,
    ScoreBreakdown,
    SignalModel,
    build_signal_direction,
    compute_prompt_hash,
)


# ---------------------------------------------------------------------------
# Helper — build a minimal valid SignalModel
# ---------------------------------------------------------------------------


def make_valid_signal(**kwargs) -> dict:
    """Return a dict of valid SignalModel fields with optional overrides."""
    score = kwargs.pop("score", 65)
    breakdown_total = score

    # Default breakdown that sums to score
    defaults = {
        "signal_id": str(uuid4()),
        "run_id": str(uuid4()),
        "langsmith_url": "https://smith.langchain.com/o/default/projects/test/runs/abc123",
        "model_version": "claude-sonnet-4-6",
        "prompt_hash": compute_prompt_hash("test prompt"),
        "generated_at": datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
        "data_latency_note": "prices are prior-day close",
        "ticker": "MP",
        "score": score,
        "score_breakdown": {
            "filing": min(breakdown_total, 30),
            "news": min(max(breakdown_total - 30, 0), 25),
            "price": min(max(breakdown_total - 55, 0), 25),
            "geo": 0,
            "novelty": 0,
        },
        "direction": build_signal_direction(score),
        "confidence": "HIGH",
        "evidence": [
            {
                "claim": "MP Materials filed 8-K disclosing new NdPr resource estimate.",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1801170/000180117024000001/mp-8k.htm",
            }
        ],
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# FilingModel validation
# ---------------------------------------------------------------------------


class TestFilingModelValidation:
    """Pydantic validation for FilingModel."""

    def test_valid_filing_model(self):
        """A complete, valid FilingModel is created without error."""
        filing = FilingModel(
            run_id=str(uuid4()),
            ticker="MP",
            form_type="8-K",
            filed_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            accession_number="0001801170-24-000001",
            document_url="https://www.sec.gov/Archives/edgar/data/1801170/000180117024000001/doc.htm",
            summary="New resource estimate at Mountain Pass.",
            source_url="https://www.sec.gov/Archives/edgar/data/1801170/000180117024000001/doc.htm",
        )
        assert filing.ticker == "MP"
        assert filing.resource_estimate_new is False  # default

    def test_missing_required_field_raises_validation_error(self):
        """Missing required field raises ValidationError, not AttributeError or KeyError."""
        with pytest.raises(ValidationError) as exc_info:
            FilingModel(
                # missing: run_id, form_type, filed_date, accession_number,
                # document_url, summary, source_url
                ticker="MP",
            )
        errors = exc_info.value.errors()
        field_names = {e["loc"][0] for e in errors}
        assert "run_id" in field_names
        assert "form_type" in field_names
        assert "filed_date" in field_names

    def test_extra_fields_are_forbidden(self):
        """FilingModel rejects extra fields (model_config extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            FilingModel(
                run_id=str(uuid4()),
                ticker="MP",
                form_type="8-K",
                filed_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
                accession_number="0001801170-24-000001",
                document_url="https://example.com/doc.htm",
                summary="Test.",
                source_url="https://example.com/doc.htm",
                hallucinated_field="this should not be here",  # extra field
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)


# ---------------------------------------------------------------------------
# ScoreBreakdown validation
# ---------------------------------------------------------------------------


class TestScoreBreakdownValidation:
    """Pydantic validation for ScoreBreakdown."""

    def test_valid_breakdown(self):
        """A valid breakdown sums correctly."""
        bd = ScoreBreakdown(filing=20, news=15, price=20, geo=10, novelty=0)
        assert bd.total == 65

    def test_filing_exceeds_max_raises_error(self):
        """filing score > 30 raises ValidationError."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(filing=31, news=0, price=0, geo=0, novelty=0)

    def test_news_exceeds_max_raises_error(self):
        """news score > 25 raises ValidationError."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(filing=0, news=26, price=0, geo=0, novelty=0)

    def test_price_exceeds_max_raises_error(self):
        """price score > 25 raises ValidationError."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(filing=0, news=0, price=26, geo=0, novelty=0)

    def test_geo_exceeds_max_raises_error(self):
        """geo score > 15 raises ValidationError."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(filing=0, news=0, price=0, geo=16, novelty=0)

    def test_novelty_exceeds_max_raises_error(self):
        """novelty score > 5 raises ValidationError."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(filing=0, news=0, price=0, geo=0, novelty=6)


# ---------------------------------------------------------------------------
# SignalModel validation (the primary LLM output guard)
# ---------------------------------------------------------------------------


class TestSignalModelValidation:
    """Pydantic validation for SignalModel — the hallucination guard."""

    def test_valid_signal_model(self):
        """A complete, valid SignalModel is created without error."""
        data = make_valid_signal(score=65)
        signal = SignalModel(**data)
        assert signal.direction == "BULL"
        assert signal.score == 65

    def test_missing_langsmith_url_raises_validation_error(self):
        """
        PRD requirement: every signal must contain LangSmith trace URL.
        Missing langsmith_url raises ValidationError.
        """
        data = make_valid_signal()
        del data["langsmith_url"]
        with pytest.raises(ValidationError) as exc_info:
            SignalModel(**data)
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "langsmith_url" for e in errors)

    def test_missing_data_latency_note_raises_validation_error(self):
        """
        PRD requirement: data_latency_note is required in every signal.
        Missing field raises ValidationError.
        """
        data = make_valid_signal()
        del data["data_latency_note"]
        with pytest.raises(ValidationError) as exc_info:
            SignalModel(**data)
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "data_latency_note" for e in errors)

    def test_missing_evidence_raises_validation_error(self):
        """Empty evidence list raises ValidationError (min_length=1)."""
        data = make_valid_signal()
        data["evidence"] = []
        with pytest.raises(ValidationError) as exc_info:
            SignalModel(**data)
        assert exc_info.value is not None

    def test_direction_mismatch_raises_validation_error(self):
        """
        Direction must be deterministically derived from score.
        Wrong direction raises ValidationError.
        """
        data = make_valid_signal(score=65)
        data["direction"] = "BEAR"  # score=65 requires BULL
        with pytest.raises(ValidationError) as exc_info:
            SignalModel(**data)
        errors = exc_info.value.errors()
        assert any("direction" in str(e) or "score" in str(e["msg"]) for e in errors)

    def test_score_breakdown_mismatch_raises_validation_error(self):
        """
        score must equal sum of score_breakdown components.
        Mismatch raises ValidationError.
        """
        data = make_valid_signal(score=65)
        # Override breakdown to sum to 50, not 65
        data["score_breakdown"] = {"filing": 20, "news": 15, "price": 10, "geo": 5, "novelty": 0}
        # total = 50, score = 65 — mismatch
        with pytest.raises(ValidationError) as exc_info:
            SignalModel(**data)
        assert exc_info.value is not None

    def test_score_out_of_range_raises_validation_error(self):
        """score must be 0–100. score=101 raises ValidationError."""
        data = make_valid_signal()
        data["score"] = 101
        with pytest.raises(ValidationError):
            SignalModel(**data)

    def test_invalid_direction_literal_raises_validation_error(self):
        """direction must be BULL, WATCH, or BEAR. Other values rejected."""
        data = make_valid_signal()
        data["direction"] = "STRONG_BUY"  # not in Literal
        with pytest.raises(ValidationError):
            SignalModel(**data)

    def test_invalid_confidence_literal_raises_validation_error(self):
        """confidence must be LOW, MED, or HIGH. Other values rejected."""
        data = make_valid_signal()
        data["confidence"] = "VERY_HIGH"  # not in Literal
        with pytest.raises(ValidationError):
            SignalModel(**data)

    def test_missing_prompt_hash_raises_validation_error(self):
        """prompt_hash is required for audit trail."""
        data = make_valid_signal()
        del data["prompt_hash"]
        with pytest.raises(ValidationError):
            SignalModel(**data)

    def test_missing_model_version_raises_validation_error(self):
        """model_version is required for audit trail."""
        data = make_valid_signal()
        del data["model_version"]
        with pytest.raises(ValidationError):
            SignalModel(**data)


# ---------------------------------------------------------------------------
# PriceModel validation
# ---------------------------------------------------------------------------


class TestPriceModelValidation:
    """Pydantic validation for PriceModel."""

    def test_rsi_out_of_range_raises_validation_error(self):
        """RSI must be 0–100."""
        with pytest.raises(ValidationError):
            PriceModel(
                ticker="MP",
                run_id=str(uuid4()),
                as_of_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
                data_latency_note="prices are prior-day close",
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                volume=1_000_000,
                rsi_14=110.0,  # invalid
            )

    def test_negative_rsi_raises_validation_error(self):
        """RSI cannot be negative."""
        with pytest.raises(ValidationError):
            PriceModel(
                ticker="MP",
                run_id=str(uuid4()),
                as_of_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
                data_latency_note="prices are prior-day close",
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                volume=1_000_000,
                rsi_14=-1.0,  # invalid
            )


# ---------------------------------------------------------------------------
# compute_prompt_hash
# ---------------------------------------------------------------------------


class TestComputePromptHash:
    """Utility tests for prompt hashing (audit trail)."""

    def test_hash_is_deterministic(self):
        """Same input always produces same hash."""
        h1 = compute_prompt_hash("test prompt")
        h2 = compute_prompt_hash("test prompt")
        assert h1 == h2

    def test_different_prompts_have_different_hashes(self):
        """Different prompts produce different hashes."""
        h1 = compute_prompt_hash("prompt A")
        h2 = compute_prompt_hash("prompt B")
        assert h1 != h2

    def test_hash_is_sha256_hex(self):
        """Hash is a 64-character hex string (SHA-256)."""
        h = compute_prompt_hash("any text")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
