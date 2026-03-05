"""
Configuration for the forum scraper.
Forum sections are sourced from canadavisa.com.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Forum sections to scrape
# ---------------------------------------------------------------------------

@dataclass
class ForumSection:
    name: str
    slug: str          # unique identifier used in filenames and DB
    url: str
    description: str
    thread_count: int  # approximate, from user context
    post_count: int    # approximate, from user context


FORUM_SECTIONS: list[ForumSection] = [
    ForumSection(
        name="Express Entry / Expression of Interest",
        slug="express-entry",
        url="https://www.canadavisa.com/canada-immigration-discussion-board/forums/express-entry-expression-of-interest.56/",
        description=(
            "Covers the Federal Skilled Worker Class, Federal Skilled Trades Class, "
            "and Canadian Experience Class under Express Entry."
        ),
        thread_count=99_400,
        post_count=1_700_000,
    ),
    ForumSection(
        name="Skilled Worker / Professional Immigration",
        slug="skilled-worker",
        url="https://www.canadavisa.com/canada-immigration-discussion-board/forums/skilled-worker-professional-immigration.5/",
        description=(
            "Canadian Permanent Residency for professional and skilled workers."
        ),
        thread_count=78_500,
        post_count=1_700_000,
    ),
    ForumSection(
        name="Canadian Experience Class",
        slug="canadian-experience-class",
        url="https://www.canadavisa.com/canada-immigration-discussion-board/forums/canadian-experience-class.40/",
        description=(
            "Immigration program for temporary foreign workers and foreign student graduates "
            "with professional, managerial and skilled work experience."
        ),
        thread_count=31_000,
        post_count=513_100,
    ),
    ForumSection(
        name="Provincial Nomination Program Immigration",
        slug="provincial-nomination",
        url="https://www.canadavisa.com/canada-immigration-discussion-board/forums/provincial-nominee-programs.9/",
        description=(
            "Provincial Nominee Programs (PNPs) allow Canadian provinces and territories "
            "to nominate individuals who wish to immigrate."
        ),
        thread_count=33_900,
        post_count=905_200,
    ),
    ForumSection(
        name="Family Class Sponsorship",
        slug="family-class-sponsorship",
        url="https://www.canadavisa.com/canada-immigration-discussion-board/forums/family-class-sponsorship.7/",
        description=(
            "How to bring family together in Canada through Canadian immigration Family Sponsorship."
        ),
        thread_count=92_700,
        post_count=2_300_000,
    ),
]


# ---------------------------------------------------------------------------
# Scraper settings
# ---------------------------------------------------------------------------

THREADS_PER_SECTION: int = int(os.getenv("SCRAPER_THREADS_PER_SECTION", "30"))
POSTS_PER_THREAD: int = int(os.getenv("SCRAPER_POSTS_PER_THREAD", "10"))
REQUEST_DELAY_SECONDS: float = float(os.getenv("SCRAPER_DELAY", "1.5"))
REQUEST_TIMEOUT: int = 30

HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

OUTPUT_DIR: Path = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Claude / Anthropic settings
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Supabase settings
# ---------------------------------------------------------------------------

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
