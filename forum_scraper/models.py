"""
Pydantic models for scraped forum data and extracted pain points.

Data flow:
    RawThread → RawPost  (from scraper)
    RawThread + RawPost  → PainPoint  (from extractor via Claude)
    PainPoint[]          → ForumSectionReport  (final JSON per section)
    ForumSectionReport[] → ScrapeRun  (full pipeline result)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Severity / Category enumerations
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"    # blocking / application rejection risk
    HIGH = "high"            # significant delay or complexity
    MEDIUM = "medium"        # moderate friction
    LOW = "low"              # minor inconvenience


class Category(str, Enum):
    DOCUMENTATION = "documentation"          # missing/wrong docs
    PROCESSING_DELAYS = "processing_delays"  # IRCC / visa office slow
    ELIGIBILITY = "eligibility"              # unclear eligibility criteria
    PORTAL_TECHNICAL = "portal_technical"    # IRCC online portal bugs
    LANGUAGE_BARRIER = "language_barrier"    # language test issues
    EMPLOYMENT = "employment"                # job offer / NOC issues
    PROOF_OF_FUNDS = "proof_of_funds"        # financial requirements
    MEDICAL_BIOMETRICS = "medical_biometrics"
    COMMUNICATION = "communication"          # lack of IRCC communication
    LEGAL_REPRESENTATION = "legal_representation"
    POINTS_CALCULATION = "points_calculation"  # CRS / score confusion
    PROVINCIAL_REQUIREMENTS = "provincial_requirements"
    SPONSORSHIP = "sponsorship"
    OTHER = "other"


class SolutionStatus(str, Enum):
    OFFICIAL = "official"          # documented IRCC / government solution
    COMMUNITY = "community"        # crowd-sourced workaround
    SPECULATIVE = "speculative"    # possible but unverified
    NONE_FOUND = "none_found"      # no solution identified


# ---------------------------------------------------------------------------
# Raw scraping models
# ---------------------------------------------------------------------------

class RawPost(BaseModel):
    post_id: str = Field(default_factory=lambda: str(uuid4()))
    author: str | None = None
    posted_at: str | None = None
    content: str
    likes: int = 0
    url: str | None = None


class RawThread(BaseModel):
    thread_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    url: str
    forum_slug: str
    author: str | None = None
    created_at: str | None = None
    reply_count: int = 0
    view_count: int = 0
    posts: list[RawPost] = Field(default_factory=list)
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Extracted pain points
# ---------------------------------------------------------------------------

class Solution(BaseModel):
    description: str = Field(
        description="Clear, actionable description of the solution or workaround."
    )
    status: SolutionStatus
    source: str | None = Field(
        None,
        description="URL or reference for official solutions (e.g., IRCC page)."
    )
    steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of concrete steps to implement the solution."
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Known limitations or conditions under which the solution may not apply."
    )
    effort: str | None = Field(
        None,
        description="Estimated effort: 'low', 'medium', 'high'."
    )


class PainPoint(BaseModel):
    pain_point_id: str = Field(default_factory=lambda: str(uuid4()))

    # Source traceability
    forum_slug: str
    thread_id: str
    thread_title: str
    thread_url: str
    evidence_quotes: list[str] = Field(
        description="Direct quotes from forum posts that demonstrate this pain point."
    )

    # Classification
    title: str = Field(description="Short, descriptive title for the pain point (max 100 chars).")
    description: str = Field(
        description="Detailed description of the problem, its context, and user impact."
    )
    category: Category
    severity: Severity
    frequency_signal: str = Field(
        description=(
            "How frequently this appears in the forum: "
            "'isolated', 'occasional', 'frequent', 'widespread'."
        )
    )

    # Affected users
    affected_user_types: list[str] = Field(
        description="Types of applicants affected, e.g. ['FSW', 'CEC', 'PNP nominees']."
    )
    affected_stages: list[str] = Field(
        description="Immigration stages affected, e.g. ['profile creation', 'ITA', 'PR card']."
    )

    # Solutions
    solutions: list[Solution] = Field(
        description="List of possible/probable solutions, ranked from most to least recommended."
    )

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Free-form tags for search.")
    extracted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Aggregated section report
# ---------------------------------------------------------------------------

class ForumSectionStats(BaseModel):
    threads_scraped: int
    posts_scraped: int
    pain_points_extracted: int
    severity_breakdown: dict[str, int]    # {"critical": 2, "high": 5, ...}
    category_breakdown: dict[str, int]    # {"documentation": 3, ...}
    top_categories: list[str]             # top 5 by count


class ForumSectionReport(BaseModel):
    section_id: str = Field(default_factory=lambda: str(uuid4()))
    forum_name: str
    forum_slug: str
    forum_url: str
    description: str
    stats: ForumSectionStats
    pain_points: list[PainPoint]
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Full pipeline run
# ---------------------------------------------------------------------------

class ScrapeRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: str
    completed_at: str | None = None
    sections_scraped: int = 0
    total_threads: int = 0
    total_posts: int = 0
    total_pain_points: int = 0
    sections: list[ForumSectionReport] = Field(default_factory=list)

    # Cross-section insights
    global_top_pain_points: list[PainPoint] = Field(
        default_factory=list,
        description="Top 10 pain points by severity + frequency across all sections."
    )
    cross_section_themes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Themes that appear across multiple forum sections."
    )

    model_config = {"extra": "forbid"}
