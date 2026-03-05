"""
Pain point extractor — uses Claude to analyse raw forum threads and
return structured PainPoint objects.

For each thread:
  1. Build a compact prompt with all post content.
  2. Ask Claude to identify pain points and solutions in JSON.
  3. Validate the response with Pydantic models.

Batching strategy:
  - Up to BATCH_SIZE threads are sent in a single prompt to reduce API calls.
  - Each batch produces a list of PainPoint objects.
"""

from __future__ import annotations

import json
import logging
from textwrap import dedent
from typing import Any

import anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from .models import (
    Category,
    PainPoint,
    RawThread,
    Severity,
    Solution,
    SolutionStatus,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 5   # threads per Claude call


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = dedent("""
You are an expert immigration analyst specialising in Canadian immigration processes
(Express Entry, CEC, PNP, Family Sponsorship, Skilled Worker).

Your task is to read forum posts from canadavisa.com and extract structured pain points
that users are experiencing, along with probable/possible solutions.

IMPORTANT:
- Be specific and concrete — avoid vague generalisations.
- Extract ONLY pain points clearly evidenced in the posts.
- For each pain point, list ALL plausible solutions (official, community workarounds, speculative).
- Use the EXACT JSON schema provided — do not add extra keys.
- severity: "critical" | "high" | "medium" | "low"
- category: one of the values listed below
- frequency_signal: "isolated" | "occasional" | "frequent" | "widespread"
- solution status: "official" | "community" | "speculative" | "none_found"
""").strip()


_CATEGORIES = [c.value for c in Category]
_SEVERITIES = [s.value for s in Severity]
_SOLUTION_STATUSES = [s.value for s in SolutionStatus]

_JSON_SCHEMA = """
{
  "pain_points": [
    {
      "title": "string (max 100 chars)",
      "description": "string — detailed context and user impact",
      "category": "one of: """ + ", ".join(_CATEGORIES) + """",
      "severity": "one of: """ + ", ".join(_SEVERITIES) + """",
      "frequency_signal": "isolated | occasional | frequent | widespread",
      "affected_user_types": ["FSW", "CEC", "PNP", "Family sponsor", ...],
      "affected_stages": ["profile creation", "ITA", "AOR", "medicals", "COPR", ...],
      "evidence_quotes": ["exact quote 1", "exact quote 2"],
      "tags": ["tag1", "tag2"],
      "solutions": [
        {
          "description": "clear actionable description",
          "status": "one of: """ + ", ".join(_SOLUTION_STATUSES) + """",
          "source": "URL or reference (optional)",
          "steps": ["step 1", "step 2"],
          "caveats": ["caveat 1"],
          "effort": "low | medium | high"
        }
      ]
    }
  ]
}
"""


def _build_user_prompt(threads: list[RawThread]) -> str:
    """Construct the user prompt for a batch of threads."""
    parts = ["Analyse the following forum threads and extract all user pain points.\n"]
    parts.append(f"Return ONLY valid JSON matching this schema:\n{_JSON_SCHEMA}\n")
    parts.append("--- THREADS ---\n")

    for t in threads:
        parts.append(f"\n[Thread] {t.title}")
        parts.append(f"URL: {t.url}")
        parts.append(f"Replies: {t.reply_count}\n")
        for i, post in enumerate(t.posts, 1):
            parts.append(f"  Post {i} (by {post.author or 'unknown'}):")
            parts.append(f"  {post.content[:1500]}\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Claude caller
# ---------------------------------------------------------------------------

def _call_claude(threads: list[RawThread]) -> list[dict[str, Any]]:
    """Call Claude API for a batch of threads; return raw pain_points list."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. "
            "Export it before running the scraper: export ANTHROPIC_API_KEY=sk-ant-..."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user_prompt = _build_user_prompt(threads)

    logger.debug("Sending %d threads to Claude (%s)", len(threads), CLAUDE_MODEL)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```", 2)[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Claude returned invalid JSON: %s\nRaw: %s", exc, raw_text[:500])
        return []

    return data.get("pain_points", [])


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _coerce_pain_point(raw: dict, thread: RawThread) -> PainPoint | None:
    """Validate and coerce a raw dict into a PainPoint, returning None on failure."""
    try:
        # Normalise enums
        raw["category"] = raw.get("category", "other")
        if raw["category"] not in _CATEGORIES:
            raw["category"] = "other"

        raw["severity"] = raw.get("severity", "medium")
        if raw["severity"] not in _SEVERITIES:
            raw["severity"] = "medium"

        raw["frequency_signal"] = raw.get("frequency_signal", "occasional")

        # Normalise solutions
        solutions_raw = raw.get("solutions", [])
        solutions: list[Solution] = []
        for s in solutions_raw:
            status = s.get("status", "speculative")
            if status not in _SOLUTION_STATUSES:
                status = "speculative"
            solutions.append(Solution(
                description=s.get("description", ""),
                status=SolutionStatus(status),
                source=s.get("source"),
                steps=s.get("steps", []),
                caveats=s.get("caveats", []),
                effort=s.get("effort"),
            ))

        return PainPoint(
            forum_slug=thread.forum_slug,
            thread_id=thread.thread_id,
            thread_title=thread.title,
            thread_url=thread.url,
            title=raw.get("title", "Untitled issue")[:100],
            description=raw.get("description", ""),
            category=Category(raw["category"]),
            severity=Severity(raw["severity"]),
            frequency_signal=raw["frequency_signal"],
            affected_user_types=raw.get("affected_user_types", []),
            affected_stages=raw.get("affected_stages", []),
            evidence_quotes=raw.get("evidence_quotes", []),
            tags=raw.get("tags", []),
            solutions=solutions,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not coerce pain point: %s | raw: %s", exc, raw)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_pain_points(threads: list[RawThread]) -> list[PainPoint]:
    """
    Extract pain points from a list of RawThreads using Claude.

    Threads are batched (BATCH_SIZE at a time) to reduce API calls.
    Returns a flat list of validated PainPoint objects.
    """
    pain_points: list[PainPoint] = []

    batches = [threads[i:i + BATCH_SIZE] for i in range(0, len(threads), BATCH_SIZE)]
    logger.info(
        "Extracting pain points from %d threads in %d batches",
        len(threads), len(batches),
    )

    for batch_idx, batch in enumerate(batches, 1):
        logger.info("Batch %d/%d — threads: %s", batch_idx, len(batches),
                    [t.title[:40] for t in batch])
        try:
            raw_items = _call_claude(batch)
        except Exception as exc:  # noqa: BLE001
            logger.error("Claude call failed for batch %d: %s", batch_idx, exc)
            continue

        for item in raw_items:
            # Assign the pain point to the first thread in the batch as default
            # (Claude may not specify which thread; we use all threads in context)
            thread = batch[0]
            pp = _coerce_pain_point(item, thread)
            if pp:
                pain_points.append(pp)

    logger.info("Total pain points extracted: %d", len(pain_points))
    return pain_points
