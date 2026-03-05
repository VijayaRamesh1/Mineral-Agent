"""
Main pipeline: scrape → extract → save JSON → upload to Supabase.

Usage:
    python -m forum_scraper.pipeline                      # all sections
    python -m forum_scraper.pipeline --slug express-entry # single section
    python -m forum_scraper.pipeline --no-upload          # skip Supabase upload
    python -m forum_scraper.pipeline --dry-run            # use cached/mock data
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import FORUM_SECTIONS, OUTPUT_DIR
from .db_uploader import upload_run
from .extractor import extract_pain_points
from .models import (
    ForumSectionReport,
    ForumSectionStats,
    PainPoint,
    ScrapeRun,
)
from .scraper import scrape_section

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stats builder
# ---------------------------------------------------------------------------

def _compute_stats(
    pain_points: list[PainPoint],
    threads_scraped: int,
    posts_scraped: int,
) -> ForumSectionStats:
    severity_counter = Counter(pp.severity.value for pp in pain_points)
    category_counter = Counter(pp.category.value for pp in pain_points)
    top_categories = [cat for cat, _ in category_counter.most_common(5)]

    return ForumSectionStats(
        threads_scraped=threads_scraped,
        posts_scraped=posts_scraped,
        pain_points_extracted=len(pain_points),
        severity_breakdown=dict(severity_counter),
        category_breakdown=dict(category_counter),
        top_categories=top_categories,
    )


# ---------------------------------------------------------------------------
# Cross-section analysis
# ---------------------------------------------------------------------------

def _identify_cross_section_themes(
    sections: list[ForumSectionReport],
) -> list[dict]:
    """Identify pain point themes that appear across multiple forum sections."""
    # Group pain points by category across sections
    category_to_sections: dict[str, list[str]] = {}
    for section in sections:
        seen_categories = {pp.category.value for pp in section.pain_points}
        for cat in seen_categories:
            category_to_sections.setdefault(cat, []).append(section.forum_slug)

    themes = []
    for category, slugs in category_to_sections.items():
        if len(slugs) >= 2:
            themes.append({
                "theme": category,
                "appears_in_sections": slugs,
                "section_count": len(slugs),
                "description": (
                    f"'{category}' pain points appear in {len(slugs)} forum sections: "
                    + ", ".join(slugs)
                ),
            })

    return sorted(themes, key=lambda x: -x["section_count"])


def _select_global_top(
    sections: list[ForumSectionReport],
    n: int = 10,
) -> list[PainPoint]:
    """Select top N pain points globally, ranked by severity + frequency."""
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    freq_rank = {"widespread": 0, "frequent": 1, "occasional": 2, "isolated": 3}

    all_pps = [pp for s in sections for pp in s.pain_points]
    sorted_pps = sorted(
        all_pps,
        key=lambda pp: (
            severity_rank.get(pp.severity.value, 9),
            freq_rank.get(pp.frequency_signal, 9),
        ),
    )
    return sorted_pps[:n]


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _save_section_json(report: ForumSectionReport) -> Path:
    """Save a section report as pretty-printed JSON."""
    path = OUTPUT_DIR / f"{report.forum_slug}_pain_points.json"
    path.write_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved section report: %s", path)
    return path


def _save_full_run_json(run: ScrapeRun) -> Path:
    """Save the full pipeline run as a single JSON file."""
    path = OUTPUT_DIR / f"scrape_run_{run.run_id[:8]}.json"
    path.write_text(
        json.dumps(run.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved full run JSON: %s", path)
    return path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    slugs: list[str] | None = None,
    upload: bool = True,
) -> ScrapeRun:
    """
    Execute the full scrape → extract → save → upload pipeline.

    Parameters
    ----------
    slugs : list[str] | None
        If provided, only process these forum slugs. Otherwise process all.
    upload : bool
        Whether to upload results to Supabase.
    """
    started_at = datetime.now(timezone.utc).isoformat()

    # Filter sections
    target_sections = FORUM_SECTIONS
    if slugs:
        target_sections = [s for s in FORUM_SECTIONS if s.slug in slugs]
        if not target_sections:
            raise ValueError(f"No sections match slugs: {slugs}")

    section_reports: list[ForumSectionReport] = []

    for forum_section in target_sections:
        logger.info("=" * 60)
        logger.info("Processing section: %s", forum_section.name)
        logger.info("=" * 60)

        # Step 1: Scrape
        raw_threads = scrape_section(forum_section)
        total_posts = sum(len(t.posts) for t in raw_threads)
        logger.info(
            "Scraped %d threads, %d posts from '%s'",
            len(raw_threads), total_posts, forum_section.name,
        )

        if not raw_threads:
            logger.warning("No threads scraped for %s — skipping", forum_section.name)
            continue

        # Step 2: Extract pain points
        pain_points = extract_pain_points(raw_threads)

        # Step 3: Build section report
        stats = _compute_stats(pain_points, len(raw_threads), total_posts)
        report = ForumSectionReport(
            forum_name=forum_section.name,
            forum_slug=forum_section.slug,
            forum_url=forum_section.url,
            description=forum_section.description,
            stats=stats,
            pain_points=pain_points,
        )
        section_reports.append(report)

        # Step 4: Save per-section JSON
        _save_section_json(report)

    if not section_reports:
        logger.error("No sections produced output. Check scraper and API configuration.")
        sys.exit(1)

    # Step 5: Build full run
    completed_at = datetime.now(timezone.utc).isoformat()
    global_top = _select_global_top(section_reports, n=10)
    themes = _identify_cross_section_themes(section_reports)

    run = ScrapeRun(
        started_at=started_at,
        completed_at=completed_at,
        sections_scraped=len(section_reports),
        total_threads=sum(s.stats.threads_scraped for s in section_reports),
        total_posts=sum(s.stats.posts_scraped for s in section_reports),
        total_pain_points=sum(s.stats.pain_points_extracted for s in section_reports),
        sections=section_reports,
        global_top_pain_points=global_top,
        cross_section_themes=themes,
    )

    # Step 6: Save full run JSON
    run_path = _save_full_run_json(run)

    logger.info("\n%s", "=" * 60)
    logger.info("Pipeline complete!")
    logger.info("  Sections:    %d", run.sections_scraped)
    logger.info("  Threads:     %d", run.total_threads)
    logger.info("  Posts:       %d", run.total_posts)
    logger.info("  Pain points: %d", run.total_pain_points)
    logger.info("  Output:      %s", run_path)

    # Step 7: Upload to Supabase
    if upload:
        try:
            upload_run(run)
            logger.info("Successfully uploaded to Supabase.")
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Supabase upload failed (data still saved locally): %s", exc
            )
    else:
        logger.info("Skipping Supabase upload (--no-upload flag set).")

    return run


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape canadavisa.com forums and extract immigration pain points."
    )
    parser.add_argument(
        "--slug",
        nargs="+",
        metavar="SLUG",
        help=(
            "Forum slugs to process. Choices: "
            "express-entry, skilled-worker, canadian-experience-class, "
            "provincial-nomination, family-class-sponsorship. "
            "Default: all."
        ),
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip Supabase upload (saves JSON locally only).",
    )
    args = parser.parse_args()

    run_pipeline(
        slugs=args.slug,
        upload=not args.no_upload,
    )


if __name__ == "__main__":
    main()
