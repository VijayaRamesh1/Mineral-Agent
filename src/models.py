"""
Pydantic models for the Critical Minerals Signal Hunter pipeline.

All agent outputs are validated through these models before being written
to AgentState. This provides a hard guarantee that invalid LLM output
raises ValidationError rather than silently propagating bad data.

Model hierarchy
---------------
FilingModel     — EDGAR filing extracted by filing_scanner
PriceModel      — OHLCV + computed metrics from price_tracker
NewsItem        — Single news article from news_sentiment
GeoEvent        — Geopolitical risk event from geo_risk
ScoreBreakdown  — Sub-scores for each signal component
EvidenceItem    — A single claim + its source URL (hallucination guard)
SignalModel     — Final per-ticker signal from signal_synthesis
ReportModel     — Metadata for the report_writer output
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Filing Scanner
# ---------------------------------------------------------------------------


class FilingModel(BaseModel):
    """Represents a single EDGAR filing extracted by Claude."""

    filing_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    ticker: str
    cik: str | None = None
    form_type: str  # e.g. "8-K", "10-Q", "10-K"
    filed_date: datetime
    period_of_report: datetime | None = None
    accession_number: str
    document_url: str

    # Claude-extracted fields
    summary: str = Field(max_length=2000)
    resource_estimate_new: bool = False      # New NI 43-101 / SK-1300 resource estimate
    resource_estimate_updated: bool = False  # Update to existing estimate
    permit_granted: bool = False             # Regulatory permit approval
    jv_announced: bool = False               # Joint venture or strategic partnership
    production_update: bool = False          # Operational / production milestone
    financing_announced: bool = False        # Equity raise, debt, offtake deal
    negative_flag: bool = False              # Adverse event (suspension, fine, writedown)
    key_entities: list[str] = Field(default_factory=list)
    source_url: str

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Price Tracker
# ---------------------------------------------------------------------------


class PriceModel(BaseModel):
    """OHLCV snapshot and deterministic computed metrics for one ticker."""

    ticker: str
    run_id: str
    as_of_date: datetime
    data_latency_note: str = Field(
        description="Must describe price lag, e.g. 'prices are prior-day close'"
    )

    # Raw OHLCV (prior-day close)
    open: float
    high: float
    low: float
    close: float
    volume: int

    # Computed metrics (deterministic — no LLM)
    return_1d: float | None = None    # 1-day return vs prior close
    return_5d: float | None = None    # 5-day return
    return_30d: float | None = None   # 30-day return
    rsi_14: float | None = None       # 14-period RSI (0–100)
    vs_remx: float | None = None      # Return relative to REMX ETF (rare earth proxy)
    vs_lit: float | None = None       # Return relative to LIT ETF (lithium proxy)

    # Score component (0–100, set by price_tracker)
    price_score: int | None = None

    @field_validator("rsi_14")
    @classmethod
    def rsi_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError(f"RSI must be 0–100, got {v}")
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# News Sentiment
# ---------------------------------------------------------------------------


class NewsItem(BaseModel):
    """A single news article scored by the news_sentiment agent."""

    item_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    ticker: str | None = None  # None = market-wide news
    headline: str
    source: str
    published_at: datetime
    url: str
    sentiment: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"] | None = None
    relevance_score: int | None = Field(None, ge=0, le=100)
    summary: str | None = Field(None, max_length=500)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Geo Risk
# ---------------------------------------------------------------------------


class GeoEvent(BaseModel):
    """A geopolitical risk event sourced from GDELT."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    country_code: str  # ISO 3166-1 alpha-2
    event_type: str    # e.g. "EXPORT_RESTRICTION", "SANCTIONS", "PROTEST"
    description: str = Field(max_length=1000)
    gdelt_url: str | None = None
    event_date: datetime
    affected_commodities: list[str] = Field(default_factory=list)
    affected_tickers: list[str] = Field(default_factory=list)

    # Claude rubric score (0–100; higher = more severe supply chain risk)
    geo_risk_score: int = Field(ge=0, le=100)
    rubric_reasoning: str = Field(max_length=500)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Signal Synthesis — building blocks
# ---------------------------------------------------------------------------


class ScoreBreakdown(BaseModel):
    """Sub-scores for each component of the composite signal score."""

    filing: int = Field(ge=0, le=30)   # max 30 per PRD weights
    news: int = Field(ge=0, le=25)     # max 25
    price: int = Field(ge=0, le=25)    # max 25
    geo: int = Field(ge=0, le=15)      # max 15
    novelty: int = Field(ge=0, le=5)   # max 5

    @model_validator(mode="after")
    def total_in_range(self) -> "ScoreBreakdown":
        total = self.filing + self.news + self.price + self.geo + self.novelty
        if not (0 <= total <= 100):
            raise ValueError(f"Total score must be 0–100, got {total}")
        return self

    @property
    def total(self) -> int:
        return self.filing + self.news + self.price + self.geo + self.novelty

    model_config = {"extra": "forbid"}


class EvidenceItem(BaseModel):
    """
    A single claim made in the signal brief, with its supporting source URL.
    Used by the hallucination guard: every claim must have a source_url.
    """

    claim: str = Field(max_length=500)
    source_url: str

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# SignalModel — the primary pipeline output
# ---------------------------------------------------------------------------


def _direction_from_score(score: int) -> Literal["BULL", "WATCH", "BEAR"]:
    """
    Deterministic mapping from composite score to signal direction.

    Thresholds (from watchlist.yaml / PRD section 7.3):
        score >= 60  →  BULL
        40 <= score < 60  →  WATCH
        score < 40   →  BEAR
    """
    if score >= 60:
        return "BULL"
    elif score >= 40:
        return "WATCH"
    else:
        return "BEAR"


class SignalModel(BaseModel):
    """
    Final per-ticker signal produced by the signal_synthesis agent.

    Every field is REQUIRED (Pydantic will raise ValidationError on missing
    fields — this is the hallucination guard for structured output).
    """

    # Audit / traceability
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    langsmith_url: str  # Direct link to LangSmith trace for this signal
    model_version: str  # e.g. "claude-sonnet-4-6"
    prompt_hash: str    # SHA-256 of the prompt(s) used for this signal
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data_latency_note: str  # e.g. "prices are prior-day close, 15-min delayed"

    # Signal content
    ticker: str
    score: int = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    direction: Literal["BULL", "WATCH", "BEAR"]
    confidence: Literal["LOW", "MED", "HIGH"]
    evidence: list[EvidenceItem] = Field(min_length=1)

    @model_validator(mode="after")
    def direction_matches_score(self) -> "SignalModel":
        """Enforce that direction is always deterministically derived from score."""
        expected = _direction_from_score(self.score)
        if self.direction != expected:
            raise ValueError(
                f"direction={self.direction!r} does not match score={self.score} "
                f"(expected {expected!r}). Direction must be derived from score."
            )
        return self

    @model_validator(mode="after")
    def score_matches_breakdown(self) -> "SignalModel":
        """Enforce that score == sum of score_breakdown components."""
        if self.score != self.score_breakdown.total:
            raise ValueError(
                f"score={self.score} != score_breakdown total={self.score_breakdown.total}"
            )
        return self

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ReportModel(BaseModel):
    """Metadata for a generated report. Content is in report_md on AgentState."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    ticker_count: int
    signal_count: int
    bull_count: int
    watch_count: int
    bear_count: int
    disclaimer_present: bool  # Must be True before any public distribution
    template_version: str = "1.0"

    @field_validator("disclaimer_present")
    @classmethod
    def disclaimer_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Legal disclaimer must be present in every report output. "
                "Set disclaimer_present=True only after confirming template includes disclaimer."
            )
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def compute_prompt_hash(prompt_text: str) -> str:
    """Return SHA-256 hex digest of a prompt string for audit trail."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def build_signal_direction(score: int) -> Literal["BULL", "WATCH", "BEAR"]:
    """Public wrapper around the deterministic direction mapping."""
    return _direction_from_score(score)
