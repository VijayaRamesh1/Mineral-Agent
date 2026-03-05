"""
Supabase uploader for pain points data.

Free DB recommendation: Supabase (https://supabase.com)
  - Free tier: 500 MB storage, 2 projects, 50,000 monthly active users
  - Postgres under the hood → full SQL power
  - Auto-generated REST API (no extra work)
  - Real-time subscriptions, built-in auth
  - Python SDK: supabase-py

Setup:
  1. Sign up at https://supabase.com (free)
  2. Create a new project
  3. Go to Settings → API and copy:
       - Project URL  → SUPABASE_URL
       - service_role key → SUPABASE_SERVICE_KEY  (keep secret!)
  4. Run the SQL migration in supabase_schema.sql (or paste into Supabase SQL editor)
  5. Set env vars:
       export SUPABASE_URL=https://<project>.supabase.co
       export SUPABASE_SERVICE_KEY=eyJ...

Tables created by this module (auto-creates via RPC if not present):
  - scrape_runs       — one row per pipeline run
  - forum_sections    — metadata per forum
  - pain_points       — individual pain points with solutions (JSONB)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .config import SUPABASE_SERVICE_KEY, SUPABASE_URL
from .models import ForumSectionReport, PainPoint, ScrapeRun

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy client initialisation (avoids import errors if supabase not installed)
# ---------------------------------------------------------------------------

def _get_client():
    """Return a Supabase client, raising a helpful error if not configured."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "Supabase is not configured.\n"
            "Set the following environment variables:\n"
            "  SUPABASE_URL=https://<project>.supabase.co\n"
            "  SUPABASE_SERVICE_KEY=<service_role_key>\n"
            "\nSee forum_scraper/supabase_schema.sql for the table definitions."
        )
    try:
        from supabase import create_client  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "supabase-py is not installed. Run: pip install supabase"
        ) from exc

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _pain_point_to_row(pp: PainPoint, run_id: str) -> dict[str, Any]:
    """Flatten a PainPoint into a database row."""
    return {
        "pain_point_id": pp.pain_point_id,
        "run_id": run_id,
        "forum_slug": pp.forum_slug,
        "thread_id": pp.thread_id,
        "thread_title": pp.thread_title,
        "thread_url": pp.thread_url,
        "title": pp.title,
        "description": pp.description,
        "category": pp.category.value,
        "severity": pp.severity.value,
        "frequency_signal": pp.frequency_signal,
        "affected_user_types": pp.affected_user_types,      # Postgres array
        "affected_stages": pp.affected_stages,               # Postgres array
        "evidence_quotes": pp.evidence_quotes,               # Postgres array
        "tags": pp.tags,                                     # Postgres array
        "solutions": json.dumps([s.model_dump() for s in pp.solutions]),  # JSONB
        "extracted_at": pp.extracted_at,
    }


def _section_to_row(section: ForumSectionReport, run_id: str) -> dict[str, Any]:
    return {
        "section_id": section.section_id,
        "run_id": run_id,
        "forum_name": section.forum_name,
        "forum_slug": section.forum_slug,
        "forum_url": section.forum_url,
        "description": section.description,
        "threads_scraped": section.stats.threads_scraped,
        "posts_scraped": section.stats.posts_scraped,
        "pain_points_extracted": section.stats.pain_points_extracted,
        "severity_breakdown": json.dumps(section.stats.severity_breakdown),
        "category_breakdown": json.dumps(section.stats.category_breakdown),
        "top_categories": section.stats.top_categories,
        "generated_at": section.generated_at,
    }


# ---------------------------------------------------------------------------
# Upload functions
# ---------------------------------------------------------------------------

def upload_run(run: ScrapeRun) -> None:
    """
    Upload a complete ScrapeRun to Supabase.

    Inserts:
      - 1 row in scrape_runs
      - N rows in forum_sections (one per section)
      - M rows in pain_points (all pain points across all sections)
    """
    client = _get_client()

    # 1. Insert scrape run record
    run_row = {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "sections_scraped": run.sections_scraped,
        "total_threads": run.total_threads,
        "total_posts": run.total_posts,
        "total_pain_points": run.total_pain_points,
        "cross_section_themes": json.dumps(run.cross_section_themes),
    }
    logger.info("Uploading scrape run %s to Supabase", run.run_id)
    response = client.table("scrape_runs").upsert(run_row).execute()
    logger.debug("scrape_runs upsert: %s", response)

    # 2. Insert forum sections
    section_rows = [_section_to_row(s, run.run_id) for s in run.sections]
    if section_rows:
        response = client.table("forum_sections").upsert(section_rows).execute()
        logger.debug("forum_sections upsert (%d rows): %s", len(section_rows), response)

    # 3. Insert all pain points
    all_pain_points = [pp for s in run.sections for pp in s.pain_points]
    # Also include global top pain points if not already in sections
    section_ids = {pp.pain_point_id for pp in all_pain_points}
    for pp in run.global_top_pain_points:
        if pp.pain_point_id not in section_ids:
            all_pain_points.append(pp)

    if all_pain_points:
        pp_rows = [_pain_point_to_row(pp, run.run_id) for pp in all_pain_points]
        # Upload in chunks to stay within Supabase row-insert limits
        chunk_size = 100
        for i in range(0, len(pp_rows), chunk_size):
            chunk = pp_rows[i:i + chunk_size]
            response = client.table("pain_points").upsert(chunk).execute()
            logger.debug(
                "pain_points upsert chunk %d-%d: %s",
                i, i + len(chunk), response
            )

    logger.info(
        "Upload complete: %d sections, %d pain points",
        len(section_rows),
        len(all_pain_points),
    )


# ---------------------------------------------------------------------------
# Utility: query pain points back from Supabase
# ---------------------------------------------------------------------------

def fetch_pain_points(
    forum_slug: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query pain points from Supabase with optional filters."""
    client = _get_client()
    query = client.table("pain_points").select("*").order("extracted_at", desc=True).limit(limit)

    if forum_slug:
        query = query.eq("forum_slug", forum_slug)
    if severity:
        query = query.eq("severity", severity)
    if category:
        query = query.eq("category", category)

    response = query.execute()
    rows = response.data or []

    # Deserialise JSONB fields
    for row in rows:
        if isinstance(row.get("solutions"), str):
            try:
                row["solutions"] = json.loads(row["solutions"])
            except json.JSONDecodeError:
                pass

    return rows
