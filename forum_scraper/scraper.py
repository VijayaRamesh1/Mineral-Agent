"""
Web scraper for canadavisa.com forum sections.

Scrapes:
  1. Forum index page → list of recent thread URLs + metadata
  2. Each thread page → post content, author, timestamps

Rate-limiting:  REQUEST_DELAY_SECONDS between requests (configurable via env).
Robots-friendly: Respects a single-threaded, polite crawl.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import (
    FORUM_SECTIONS,
    ForumSection,
    HEADERS,
    POSTS_PER_THREAD,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    THREADS_PER_SECTION,
)
from .models import RawPost, RawThread

logger = logging.getLogger(__name__)

BASE_URL = "https://www.canadavisa.com"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, session: requests.Session) -> BeautifulSoup | None:
    """Fetch URL and return BeautifulSoup, or None on failure."""
    try:
        response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _sleep() -> None:
    time.sleep(REQUEST_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# Thread listing parser
# ---------------------------------------------------------------------------

def _parse_thread_list(soup: BeautifulSoup, forum_slug: str) -> list[dict]:
    """
    Parse the forum index page and return a list of thread metadata dicts.
    Handles XenForo-based forum structure used by canadavisa.com.
    """
    threads = []

    # XenForo thread rows are <div class="structItem"> or <li class="discussionListItem">
    rows = (
        soup.select("div.structItem--thread")
        or soup.select("li.discussionListItem")
        or soup.select("div.js-threadList div.structItem")
    )

    for row in rows:
        try:
            # Thread title / URL
            title_el = (
                row.select_one("div.structItem-title a[data-tp-primary]")
                or row.select_one("a.PreviewTooltip")
                or row.select_one("h3.title a")
                or row.select_one("a.item-title")
            )
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = urljoin(BASE_URL, href)

            # Author
            author_el = (
                row.select_one("a.username")
                or row.select_one("span.username")
            )
            author = author_el.get_text(strip=True) if author_el else None

            # Reply / view counts
            reply_el = row.select_one("dl.pairs--justDt dd") or row.select_one("span.count")
            reply_count = 0
            if reply_el:
                try:
                    reply_count = int(re.sub(r"[^\d]", "", reply_el.get_text()))
                except ValueError:
                    pass

            threads.append({
                "title": title,
                "url": url,
                "forum_slug": forum_slug,
                "author": author,
                "reply_count": reply_count,
            })

        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping malformed thread row: %s", exc)
            continue

    return threads


# ---------------------------------------------------------------------------
# Thread / post parser
# ---------------------------------------------------------------------------

def _parse_thread(
    soup: BeautifulSoup,
    thread_meta: dict,
    max_posts: int,
) -> RawThread:
    """Extract posts from a thread page."""
    posts: list[RawPost] = []

    # XenForo post articles: <article class="message">
    articles = (
        soup.select("article.message--post")
        or soup.select("li.message")
        or soup.select("div.messageList div.message")
    )

    for article in articles[:max_posts]:
        try:
            # Author
            author_el = (
                article.select_one("a.username")
                or article.select_one("span.username")
            )
            author = author_el.get_text(strip=True) if author_el else None

            # Timestamp
            time_el = article.select_one("time")
            posted_at = time_el.get("datetime") or time_el.get_text(strip=True) if time_el else None

            # Post body — strip quotes/blockquotes to avoid noise
            body_el = (
                article.select_one("div.message-body div.bbWrapper")
                or article.select_one("div.messageText")
                or article.select_one("blockquote.messageText")
            )
            if body_el:
                # Remove nested quoted content
                for quote in body_el.select("div.bbCodeBlock--quote, blockquote"):
                    quote.decompose()
                content = body_el.get_text(separator=" ", strip=True)
            else:
                content = ""

            if len(content) < 20:
                continue

            # Likes / reactions
            likes_el = article.select_one("span.reactionsBar-link") or article.select_one("span.like-count")
            likes = 0
            if likes_el:
                try:
                    likes = int(re.sub(r"[^\d]", "", likes_el.get_text()))
                except ValueError:
                    pass

            posts.append(RawPost(
                author=author,
                posted_at=posted_at,
                content=content[:3000],  # cap per post
                likes=likes,
                url=thread_meta["url"],
            ))

        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping malformed post: %s", exc)
            continue

    return RawThread(
        title=thread_meta["title"],
        url=thread_meta["url"],
        forum_slug=thread_meta["forum_slug"],
        author=thread_meta.get("author"),
        reply_count=thread_meta.get("reply_count", 0),
        posts=posts,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_section(section: ForumSection) -> list[RawThread]:
    """
    Scrape one forum section: fetch the index, collect thread URLs,
    then fetch each thread and extract posts.

    Returns a list of RawThread objects.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    logger.info("Scraping section: %s", section.name)
    index_soup = _get(section.url, session)
    if index_soup is None:
        logger.error("Could not fetch forum index for %s", section.name)
        return []

    thread_metas = _parse_thread_list(index_soup, section.slug)
    logger.info("Found %d thread links on index page", len(thread_metas))

    # Trim to requested count
    thread_metas = thread_metas[:THREADS_PER_SECTION]

    raw_threads: list[RawThread] = []
    for i, meta in enumerate(thread_metas, 1):
        logger.info("[%d/%d] Fetching thread: %s", i, len(thread_metas), meta["title"][:60])
        _sleep()
        thread_soup = _get(meta["url"], session)
        if thread_soup is None:
            logger.warning("Skipping thread (fetch failed): %s", meta["url"])
            continue
        thread = _parse_thread(thread_soup, meta, max_posts=POSTS_PER_THREAD)
        if thread.posts:
            raw_threads.append(thread)
        else:
            logger.debug("Thread had no parseable posts, skipping: %s", meta["title"])

    logger.info(
        "Section %s: scraped %d threads with %d total posts",
        section.slug,
        len(raw_threads),
        sum(len(t.posts) for t in raw_threads),
    )
    return raw_threads


def scrape_all_sections() -> dict[str, list[RawThread]]:
    """Scrape all configured forum sections and return {slug: [RawThread]}."""
    results: dict[str, list[RawThread]] = {}
    for section in FORUM_SECTIONS:
        results[section.slug] = scrape_section(section)
        _sleep()  # extra pause between sections
    return results
