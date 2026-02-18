"""
test_report_writer.py — Phase 4 deliverable tests.

Covers:
  - report_writer_node: Jinja2 template rendering, disclaimer presence,
    ReportModel validation, correct direction/ticker content.
  - memory_agent_node: SQLite persistence calls, empty state handling.
  - src.db helpers: init_db, persist_signal, persist_run, query_signals.
  - ReportModel Pydantic validation guard (disclaimer_present required).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.agents.report_writer import LEGAL_DISCLAIMER, memory_agent_node, report_writer_node
from src.db import init_db, persist_run, persist_signal, query_signals
from src.models import ReportModel, build_signal_direction, compute_prompt_hash


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_signal_dict(ticker: str = "MP", score: int = 65) -> dict:
    """Build a minimal valid signal dict (mirrors signal_synthesis output)."""
    filing = min(score, 30)
    news = min(max(score - 30, 0), 25)
    price = min(max(score - 55, 0), 25)
    run_id = str(uuid4())
    return {
        "signal_id": str(uuid4()),
        "run_id": run_id,
        "langsmith_url": f"https://smith.langchain.com/o/test/projects/p/runs/{run_id}",
        "model_version": "gemini-2.0-flash",
        "prompt_hash": compute_prompt_hash(f"test prompt for {ticker}"),
        "generated_at": datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
        "data_latency_note": "prices are prior-day close",
        "ticker": ticker,
        "score": score,
        "score_breakdown": {
            "filing": filing,
            "news": news,
            "price": price,
            "geo": 0,
            "novelty": 0,
        },
        "direction": build_signal_direction(score),
        "confidence": "HIGH",
        "evidence": [
            {
                "claim": f"{ticker} filed 8-K with significant development.",
                "source_url": (
                    f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=8-K"
                ),
            }
        ],
    }


@pytest.fixture
def sample_state():
    """AgentState-like dict with two signals (BULL + WATCH)."""
    run_id = str(uuid4())
    return {
        "run_id": run_id,
        "watchlist": ["MP", "UUUU"],
        "filings": [],
        "news_items": [],
        "prices": {},
        "geo_events": [],
        "signals": [
            _make_signal_dict("MP", 65),   # BULL
            _make_signal_dict("UUUU", 45), # WATCH
        ],
        "errors": [],
        "report_md": "",
    }


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database initialised with the schema."""
    db_path = tmp_path / "test_signals.db"
    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# report_writer_node
# ---------------------------------------------------------------------------


class TestReportWriterNode:

    def test_returns_report_md_key(self, sample_state):
        """report_writer_node returns a dict with the 'report_md' key."""
        result = report_writer_node(sample_state)
        assert "report_md" in result

    def test_report_contains_disclaimer(self, sample_state):
        """Rendered report always contains 'DISCLAIMER'."""
        result = report_writer_node(sample_state)
        assert "DISCLAIMER" in result["report_md"]

    def test_report_contains_ticker_symbols(self, sample_state):
        """Report body includes the ticker symbols from signals."""
        result = report_writer_node(sample_state)
        assert "MP" in result["report_md"]
        assert "UUUU" in result["report_md"]

    def test_report_contains_run_id(self, sample_state):
        """Report includes the run ID for traceability."""
        result = report_writer_node(sample_state)
        assert sample_state["run_id"] in result["report_md"]

    def test_report_is_nonempty_string(self, sample_state):
        """report_md is a non-empty string with meaningful content."""
        result = report_writer_node(sample_state)
        assert isinstance(result["report_md"], str)
        assert len(result["report_md"]) > 100

    def test_report_contains_bull_direction(self, sample_state):
        """Report includes BULL direction for score=65 signal."""
        result = report_writer_node(sample_state)
        assert "BULL" in result["report_md"]

    def test_report_contains_watch_direction(self, sample_state):
        """Report includes WATCH direction for score=45 signal."""
        result = report_writer_node(sample_state)
        assert "WATCH" in result["report_md"]

    def test_empty_signals_still_produces_disclaimer(self):
        """With no signals, report still contains the legal disclaimer."""
        state = {
            "run_id": str(uuid4()),
            "watchlist": [],
            "signals": [],
            "errors": [],
            "report_md": "",
        }
        result = report_writer_node(state)
        assert "DISCLAIMER" in result["report_md"]

    def test_empty_signals_returns_string(self):
        """With no signals, report_md is still a non-empty string."""
        state = {
            "run_id": str(uuid4()),
            "watchlist": [],
            "signals": [],
            "errors": [],
            "report_md": "",
        }
        result = report_writer_node(state)
        assert isinstance(result["report_md"], str)
        assert len(result["report_md"]) > 0

    def test_report_contains_score(self, sample_state):
        """Report includes the numeric score from each signal."""
        result = report_writer_node(sample_state)
        # MP score=65, UUUU score=45
        assert "65" in result["report_md"]
        assert "45" in result["report_md"]

    def test_single_signal_report(self):
        """report_writer_node handles a single signal correctly."""
        state = {
            "run_id": str(uuid4()),
            "watchlist": ["MP"],
            "signals": [_make_signal_dict("MP", 70)],
            "errors": [],
            "report_md": "",
        }
        result = report_writer_node(state)
        assert "DISCLAIMER" in result["report_md"]
        assert "MP" in result["report_md"]


# ---------------------------------------------------------------------------
# memory_agent_node
# ---------------------------------------------------------------------------


class TestMemoryAgentNode:

    def test_returns_empty_dict(self, sample_state):
        """memory_agent_node returns {} — no state mutations."""
        result = memory_agent_node(sample_state)
        assert result == {}

    def test_persist_signal_called_for_each_signal(self, sample_state, monkeypatch):
        """memory_agent_node calls persist_signal once per signal."""
        import src.agents.report_writer as rw

        persisted_tickers: list[str] = []

        def fake_persist_signal(d):
            persisted_tickers.append(d.get("ticker"))

        monkeypatch.setattr(rw, "persist_signal", fake_persist_signal)
        monkeypatch.setattr(rw, "persist_run", lambda **kw: None)

        memory_agent_node(sample_state)

        assert sorted(persisted_tickers) == ["MP", "UUUU"]

    def test_persist_run_called_once(self, sample_state, monkeypatch):
        """memory_agent_node calls persist_run exactly once."""
        import src.agents.report_writer as rw

        run_calls: list[str] = []

        monkeypatch.setattr(rw, "persist_signal", lambda d: None)
        monkeypatch.setattr(
            rw, "persist_run", lambda run_id, **kw: run_calls.append(run_id)
        )

        memory_agent_node(sample_state)

        assert len(run_calls) == 1
        assert run_calls[0] == sample_state["run_id"]

    def test_empty_signals_does_not_raise(self):
        """memory_agent_node handles empty state without error."""
        state = {
            "run_id": str(uuid4()),
            "watchlist": [],
            "signals": [],
            "errors": [],
            "report_md": "",
        }
        result = memory_agent_node(state)
        assert result == {}

    def test_persist_signal_failure_does_not_crash(self, sample_state, monkeypatch):
        """A failing persist_signal does not propagate — other signals proceed."""
        import src.agents.report_writer as rw

        call_count = [0]

        def flaky_persist(d):
            call_count[0] += 1
            if d.get("ticker") == "MP":
                raise RuntimeError("simulated DB failure")

        monkeypatch.setattr(rw, "persist_signal", flaky_persist)
        monkeypatch.setattr(rw, "persist_run", lambda run_id, **kw: None)

        result = memory_agent_node(sample_state)
        assert result == {}
        assert call_count[0] == 2  # both signals attempted


# ---------------------------------------------------------------------------
# SQLite persistence helpers (src.db)
# ---------------------------------------------------------------------------


class TestInitDb:

    def test_creates_runs_table(self, tmp_db):
        """init_db creates the 'runs' table."""
        conn = sqlite3.connect(str(tmp_db))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "runs" in tables

    def test_creates_signals_table(self, tmp_db):
        """init_db creates the 'signals' table."""
        conn = sqlite3.connect(str(tmp_db))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "signals" in tables

    def test_idempotent(self, tmp_db):
        """Calling init_db twice does not raise."""
        init_db(tmp_db)  # second call
        init_db(tmp_db)  # third call — still no error


class TestPersistAndQuerySignal:

    def test_persist_and_query_roundtrip(self, tmp_db):
        """A persisted signal can be retrieved with query_signals."""
        signal = _make_signal_dict("MP", 65)
        persist_signal(signal, db_path=tmp_db)

        results = query_signals(db_path=tmp_db)
        assert len(results) == 1
        row = results[0]
        assert row["ticker"] == "MP"
        assert row["score"] == 65
        assert row["direction"] == "BULL"

    def test_score_breakdown_deserialized_as_dict(self, tmp_db):
        """score_breakdown is returned as a Python dict (not a JSON string)."""
        signal = _make_signal_dict("MP", 65)
        persist_signal(signal, db_path=tmp_db)

        results = query_signals(db_path=tmp_db)
        breakdown = results[0]["score_breakdown"]
        assert isinstance(breakdown, dict)
        assert "filing" in breakdown
        assert "news" in breakdown

    def test_evidence_deserialized_as_list(self, tmp_db):
        """evidence is returned as a Python list (not a JSON string)."""
        signal = _make_signal_dict("MP", 65)
        persist_signal(signal, db_path=tmp_db)

        results = query_signals(db_path=tmp_db)
        evidence = results[0]["evidence"]
        assert isinstance(evidence, list)
        assert len(evidence) >= 1
        assert "claim" in evidence[0]
        assert "source_url" in evidence[0]

    def test_filter_by_ticker(self, tmp_db):
        """query_signals(ticker=...) returns only matching rows."""
        persist_signal(_make_signal_dict("MP", 65), db_path=tmp_db)
        persist_signal(_make_signal_dict("UUUU", 45), db_path=tmp_db)

        mp_signals = query_signals(ticker="MP", db_path=tmp_db)
        assert len(mp_signals) == 1
        assert mp_signals[0]["ticker"] == "MP"

    def test_filter_by_ticker_case_insensitive(self, tmp_db):
        """Ticker filter is normalised to uppercase."""
        persist_signal(_make_signal_dict("MP", 65), db_path=tmp_db)

        results = query_signals(ticker="mp", db_path=tmp_db)
        assert len(results) == 1

    def test_limit_respected(self, tmp_db):
        """query_signals respects the limit parameter."""
        for _ in range(5):
            signal = _make_signal_dict("MP", 65)
            signal["signal_id"] = str(uuid4())  # unique IDs
            persist_signal(signal, db_path=tmp_db)

        results = query_signals(limit=3, db_path=tmp_db)
        assert len(results) == 3

    def test_insert_or_replace(self, tmp_db):
        """Re-inserting the same signal_id replaces the existing row."""
        signal = _make_signal_dict("MP", 65)
        persist_signal(signal, db_path=tmp_db)

        # Update score and re-insert same signal_id
        signal["score"] = 70
        signal["score_breakdown"]["filing"] = 30
        signal["score_breakdown"]["price"] = 15
        persist_signal(signal, db_path=tmp_db)

        results = query_signals(db_path=tmp_db)
        assert len(results) == 1  # still one row
        assert results[0]["score"] == 70


class TestPersistRun:

    def test_persist_and_retrieve_run(self, tmp_db):
        """persist_run stores run metadata and it is queryable."""
        run_id = str(uuid4())
        persist_run(
            run_id, ticker_count=15, signal_count=12, error_count=0, db_path=tmp_db
        )

        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["run_id"] == run_id
        assert row["ticker_count"] == 15
        assert row["signal_count"] == 12
        assert row["error_count"] == 0

    def test_persist_run_with_report_md(self, tmp_db):
        """persist_run stores the report_md field."""
        run_id = str(uuid4())
        persist_run(
            run_id,
            ticker_count=2,
            signal_count=2,
            error_count=0,
            report_md="# Report\n\nDISCLAIMER: test",
            db_path=tmp_db,
        )

        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT report_md FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        conn.close()

        assert "DISCLAIMER" in row["report_md"]


# ---------------------------------------------------------------------------
# ReportModel Pydantic validation (Phase 4 guard)
# ---------------------------------------------------------------------------


class TestReportModelValidation:

    def test_valid_report_model(self):
        """A complete ReportModel with disclaimer_present=True is valid."""
        report = ReportModel(
            run_id=str(uuid4()),
            ticker_count=15,
            signal_count=12,
            bull_count=5,
            watch_count=4,
            bear_count=3,
            disclaimer_present=True,
        )
        assert report.signal_count == 12
        assert report.template_version == "1.0"

    def test_disclaimer_false_raises_validation_error(self):
        """disclaimer_present=False raises ValidationError (PRD requirement)."""
        with pytest.raises(ValidationError) as exc_info:
            ReportModel(
                run_id=str(uuid4()),
                ticker_count=15,
                signal_count=12,
                bull_count=5,
                watch_count=4,
                bear_count=3,
                disclaimer_present=False,
            )
        errors = exc_info.value.errors()
        assert any("disclaimer" in str(e).lower() for e in errors)

    def test_missing_run_id_raises_validation_error(self):
        """Missing run_id raises ValidationError."""
        with pytest.raises(ValidationError):
            ReportModel(
                ticker_count=2,
                signal_count=2,
                bull_count=1,
                watch_count=1,
                bear_count=0,
                disclaimer_present=True,
            )

    def test_default_template_version(self):
        """template_version defaults to '1.0'."""
        report = ReportModel(
            run_id=str(uuid4()),
            ticker_count=2,
            signal_count=2,
            bull_count=1,
            watch_count=1,
            bear_count=0,
            disclaimer_present=True,
        )
        assert report.template_version == "1.0"

    def test_zero_signals_is_valid(self):
        """A report with zero signals is valid (pipeline may run with no data)."""
        report = ReportModel(
            run_id=str(uuid4()),
            ticker_count=15,
            signal_count=0,
            bull_count=0,
            watch_count=0,
            bear_count=0,
            disclaimer_present=True,
        )
        assert report.signal_count == 0
