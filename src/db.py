"""
SQLite persistence helpers for the Critical Minerals Signal Hunter.

Uses Python's stdlib sqlite3 — no extra dependencies required.

Tables
------
runs:
    run_id TEXT PRIMARY KEY
    started_at TEXT
    ticker_count INTEGER
    signal_count INTEGER
    error_count INTEGER
    report_md TEXT

signals:
    signal_id TEXT PRIMARY KEY
    run_id TEXT
    ticker TEXT
    score INTEGER
    direction TEXT
    confidence TEXT
    score_breakdown TEXT  (JSON)
    evidence TEXT         (JSON)
    model_version TEXT
    prompt_hash TEXT
    generated_at TEXT
    data_latency_note TEXT
    langsmith_url TEXT
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _db_path() -> Path:
    """Resolve SQLite file path from settings.database_url.

    Supports sqlite:///./path/to/db and sqlite:////abs/path formats.
    """
    url = settings.database_url  # e.g. "sqlite:///./data/signals.db"
    if url.startswith("sqlite:///"):
        path = Path(url[len("sqlite:///"):])
    else:
        path = Path("data/signals.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a sqlite3 connection with Row factory enabled."""
    path = db_path if db_path is not None else _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------


def init_db(db_path: Path | None = None) -> None:
    """Create tables and indexes if they do not already exist."""
    conn = _connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id       TEXT PRIMARY KEY,
                started_at   TEXT NOT NULL,
                ticker_count INTEGER NOT NULL DEFAULT 0,
                signal_count INTEGER NOT NULL DEFAULT 0,
                error_count  INTEGER NOT NULL DEFAULT 0,
                report_md    TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS signals (
                signal_id         TEXT PRIMARY KEY,
                run_id            TEXT NOT NULL,
                ticker            TEXT NOT NULL,
                score             INTEGER NOT NULL,
                direction         TEXT NOT NULL,
                confidence        TEXT NOT NULL,
                score_breakdown   TEXT NOT NULL,
                evidence          TEXT NOT NULL,
                model_version     TEXT NOT NULL,
                prompt_hash       TEXT NOT NULL,
                generated_at      TEXT NOT NULL,
                data_latency_note TEXT NOT NULL,
                langsmith_url     TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_signals_run_id
                ON signals(run_id);
            CREATE INDEX IF NOT EXISTS idx_signals_ticker
                ON signals(ticker);
            CREATE INDEX IF NOT EXISTS idx_signals_generated_at
                ON signals(generated_at);
        """)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def persist_run(
    run_id: str,
    ticker_count: int,
    signal_count: int,
    error_count: int,
    report_md: str = "",
    db_path: Path | None = None,
) -> None:
    """Insert or replace a pipeline run record."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
                (run_id, started_at, ticker_count, signal_count, error_count, report_md)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                ticker_count,
                signal_count,
                error_count,
                report_md,
            ),
        )
        conn.commit()
        logger.debug("db.persist_run: saved run_id=%s", run_id)
    finally:
        conn.close()


def persist_signal(signal_dict: dict[str, Any], db_path: Path | None = None) -> None:
    """Insert or replace a signal record.

    Parameters
    ----------
    signal_dict : dict
        A SignalModel.model_dump() result. score_breakdown and evidence
        are serialised to JSON for storage.
    db_path : Path, optional
        Override the database path (used in tests).
    """
    init_db(db_path)

    breakdown = signal_dict.get("score_breakdown", {})
    if not isinstance(breakdown, dict):
        breakdown = {}

    evidence = signal_dict.get("evidence", [])
    if evidence and not isinstance(evidence[0], dict):
        evidence = [dict(e) for e in evidence]

    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO signals
                (signal_id, run_id, ticker, score, direction, confidence,
                 score_breakdown, evidence, model_version, prompt_hash,
                 generated_at, data_latency_note, langsmith_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(signal_dict.get("signal_id", "")),
                str(signal_dict.get("run_id", "")),
                str(signal_dict.get("ticker", "")),
                int(signal_dict.get("score", 0)),
                str(signal_dict.get("direction", "")),
                str(signal_dict.get("confidence", "")),
                json.dumps(breakdown),
                json.dumps(evidence),
                str(signal_dict.get("model_version", "")),
                str(signal_dict.get("prompt_hash", "")),
                str(signal_dict.get("generated_at", "")),
                str(signal_dict.get("data_latency_note", "")),
                str(signal_dict.get("langsmith_url", "")),
            ),
        )
        conn.commit()
        logger.debug(
            "db.persist_signal: saved signal_id=%s ticker=%s",
            signal_dict.get("signal_id"),
            signal_dict.get("ticker"),
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def query_signals(
    ticker: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Query recent signals from the database.

    Parameters
    ----------
    ticker : str, optional
        Filter to a specific ticker symbol (case-insensitive).
    limit : int
        Maximum number of rows to return, ordered by generated_at DESC.
    db_path : Path, optional
        Override the database path (used in tests).

    Returns
    -------
    list of dicts
        Each dict contains all signal columns; score_breakdown and
        evidence are deserialized from JSON back to Python objects.
    """
    init_db(db_path)
    conn = _connect(db_path)
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM signals WHERE ticker = ? ORDER BY generated_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()

    results: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        try:
            d["score_breakdown"] = json.loads(d["score_breakdown"])
        except (json.JSONDecodeError, KeyError):
            pass
        try:
            d["evidence"] = json.loads(d["evidence"])
        except (json.JSONDecodeError, KeyError):
            pass
        results.append(d)
    return results
