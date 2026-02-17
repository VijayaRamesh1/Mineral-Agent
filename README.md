# Critical Minerals Signal Hunter

A multi-agent pipeline that monitors EDGAR filings, news, price data, and geopolitical events for 15 critical minerals tickers — producing daily scored signals for a Substack/Telegram newsletter.

**Status: Phase 0 — Scaffold complete. Phase 1 in development.**

---

## Architecture

```
orchestrator
     │
filing_scanner ──────── EDGAR EFTS → 8-K download → Claude extraction → FilingModel
     │
news_sentiment ─┐
price_tracker  ─┼─ (parallel in Phase 1+, via LangGraph Send API)
geo_risk        ─┘
     │
signal_synthesis ─── Deterministic scoring rubric + Claude (temp=0) → SignalModel
     │
report_writer ──── Jinja2 template (no LLM) → Markdown report
     │
memory_agent ──── SQLite persistence (signals, runs, watchlist)
```

**LangGraph** orchestrates the DAG. **LangSmith** traces every node. Every signal output contains a direct LangSmith trace URL for full auditability.

---

## Watchlist (v1.0 — 15 Tickers)

| Ticker | Company | Sector |
|--------|---------|--------|
| MP | MP Materials | Rare Earth |
| UUUU | Energy Fuels | Uranium + REE |
| NB | NioCorp Developments | REE + Niobium |
| PLL | Piedmont Lithium | Lithium |
| PMETF | Patriot Battery Metals | Lithium |
| LYSCF | Lynas Rare Earths | Rare Earth (ex-China) |
| REEMF | Rare Element Resources | Rare Earth |
| UAMY | United States Antimony | Antimony |
| NOVRF | Nouveau Monde Graphite | Graphite |
| GIGA | Gigametals | Nickel/Cobalt |
| URG | Ur-Energy | Uranium |
| DNN | Denison Mines | Uranium |
| REMX | VanEck Rare Earth ETF | ETF Proxy |
| LIT | Global X Lithium ETF | ETF Proxy |
| COPX | Global X Copper Miners ETF | ETF Proxy |

---

## Tech Stack

| Component | Version |
|-----------|---------|
| Python | 3.12 |
| LangGraph | >=0.2 |
| LangSmith | >=0.1 |
| Claude | claude-sonnet-4-6 (temp=0) |
| FastAPI | >=0.110 |
| yfinance | ==0.2.38 (pinned) |
| Pydantic | >=2.0 |
| SQLite | stdlib |
| Docker | python:3.12-slim |

---

## Quick Start

### Prerequisites

- Python 3.12
- Docker (optional)
- Anthropic API key
- LangSmith account (free tier — 5k traces/month)

### Local Setup

```bash
# Clone and enter repo
git clone <repo-url>
cd critical-minerals-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and LANGCHAIN_API_KEY

# Run tests (Phase 0: deterministic tests pass, Phase 1+ tests intentionally fail)
pytest -m "not integration"

# Start FastAPI server
uvicorn src.api:app --reload --port 8000

# Trigger a pipeline run (Phase 0: stub response)
curl -X POST http://localhost:8000/run
```

### Docker

```bash
# Build
docker build -t critical-minerals-agent .

# Run (requires .env file)
docker compose up agent

# One-shot pipeline run
docker compose --profile run up pipeline
```

---

## Signal Model

Every signal output contains these fields (all required — missing fields raise `ValidationError`):

```json
{
  "signal_id": "uuid",
  "run_id": "uuid",
  "langsmith_url": "https://smith.langchain.com/...",
  "ticker": "MP",
  "score": 65,
  "score_breakdown": {
    "filing": 20,
    "news": 15,
    "price": 20,
    "geo": 10,
    "novelty": 0
  },
  "direction": "BULL",
  "confidence": "HIGH",
  "evidence": [
    {
      "claim": "MP Materials filed 8-K disclosing expanded NdPr resource estimate.",
      "source_url": "https://www.sec.gov/..."
    }
  ],
  "model_version": "claude-sonnet-4-6",
  "prompt_hash": "sha256-of-prompt",
  "generated_at": "2024-01-15T09:00:00Z",
  "data_latency_note": "prices are prior-day close; 15-min delayed"
}
```

**Score → Direction thresholds:**
- `score >= 60` → `BULL`
- `40 <= score < 60` → `WATCH`
- `score < 40` → `BEAR`

Direction is **deterministically derived from score** — Claude never decides direction.

---

## Scoring Rubric

| Component | Max Weight | Source |
|-----------|-----------|--------|
| Filing | 30 | EDGAR 8-K extraction |
| News | 25 | RSS feeds + GDELT |
| Price | 25 | yfinance (OHLCV + RSI + REMX/LIT relative) |
| Geo Risk | 15 | GDELT + Claude rubric |
| Novelty | 5 | Delta vs prior SQLite signal |
| **Total** | **100** | |

---

## Testing

```bash
# Run all non-integration tests
pytest -m "not integration"

# Run with coverage
pytest --cov=src --cov-report=term-missing -m "not integration"

# Run specific test file
pytest tests/test_signal_direction.py -v

# Phase 0 expected status:
#   test_signal_direction.py  — PASS (deterministic mapping implemented)
#   test_pydantic_validation.py — PASS (Pydantic works)
#   test_score_components.py  — SKIP/FAIL (Phase 3 deliverable)
#   test_price_momentum.py    — SKIP/FAIL (Phase 2 deliverable)
#   test_edgar_query.py       — SKIP/FAIL (Phase 1 deliverable)
```

---

## Build Phases

| Phase | Status | Deliverables |
|-------|--------|-------------|
| **Phase 0** | ✅ Complete | Repo scaffold, state schema, Pydantic models, LangGraph stubs, pytest skeleton, Docker |
| **Phase 1** | 🔄 Next | EDGAR EFTS query, 8-K download, Claude extraction, FilingModel tests |
| **Phase 2** | Pending | yfinance integration, RSI/momentum, GDELT geo risk |
| **Phase 3** | Pending | Signal Synthesis, LangSmith eval dataset, hallucination guard |
| **Phase 4** | Pending | Report Writer (Jinja2), Telegram, SQLite, FastAPI, APScheduler |
| **Phase 5** | Pending | Hardening, Docker build test, GitHub Actions health check |

---

## Acceptance Criteria (v1.0)

Before first free subscriber:

- [ ] `pytest` passes (≥95% coverage on deterministic components)
- [ ] LangSmith golden eval ≥85% accuracy on 20 test cases
- [ ] Every signal contains LangSmith trace URL
- [ ] Hallucination guard rejects evidence-free claims
- [ ] Full pipeline runs on 15 tickers in <8 minutes
- [ ] Docker build succeeds on clean machine
- [ ] Legal disclaimer in every report output
- [ ] `data_latency_note` in every Signal (Pydantic required field)
- [ ] 3 consecutive daily runs without error
- [ ] GitHub Actions CI green

---

## Legal

This system generates automated signals for informational purposes only. Nothing in its output constitutes financial advice, investment recommendations, or solicitation to buy or sell securities. Always conduct your own due diligence.

---

## Project Structure

```
critical-minerals-agent/
├── src/
│   ├── agents/
│   │   ├── orchestrator.py      # Pipeline entry point
│   │   ├── filing_scanner.py    # EDGAR 8-K extraction (Phase 1)
│   │   ├── news_sentiment.py    # RSS + sentiment (Phase 2)
│   │   ├── price_tracker.py     # yfinance + RSI (Phase 2)
│   │   ├── geo_risk.py          # GDELT + Claude rubric (Phase 2)
│   │   ├── signal_synthesis.py  # Scoring + SignalModel (Phase 3)
│   │   └── report_writer.py     # Jinja2 report + SQLite (Phase 4)
│   ├── state.py                 # TypedDict AgentState
│   ├── models.py                # Pydantic models (all agents)
│   ├── graph.py                 # LangGraph StateGraph
│   ├── tracing.py               # LangSmith wrapper
│   ├── config.py                # pydantic-settings config
│   └── api.py                   # FastAPI endpoints
├── tests/
│   ├── fixtures/                # Real EDGAR filings (Phase 1+)
│   ├── test_signal_direction.py
│   ├── test_score_components.py
│   ├── test_pydantic_validation.py
│   ├── test_price_momentum.py
│   └── test_edgar_query.py
├── templates/
│   └── report.md.j2             # Report template (Phase 4)
├── data/                        # SQLite database (gitignored)
├── watchlist.yaml               # 15-ticker watchlist
├── run_pipeline.py              # CLI entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── .env.example
```
