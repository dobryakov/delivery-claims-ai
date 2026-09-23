# delivery-claims-ai

Educational project: AI-assisted triage of delivery-delay complaints, built with
**LangGraph** (agent workflow) and **LangSmith** (tracing, datasets, evaluation).

A customer complains that an order arrived late. The system classifies the
complaint, extracts the order id, looks up promised vs. actual delivery from a
mock database, and an **LLM judge** decides whether the complaint is justified.
The result is sent to a manager for review (human-in-the-loop) before it is
finalized.

See [docs/specs.md](docs/specs.md) for the full specification.

## Design in one line

Code owns the facts (dates, delay, money); the LLM owns the judgment (justified
or not, what to offer). See specs §2.

## Setup

```bash
cp .env.example .env   # then fill in OPENROUTER_API_KEY and LANGSMITH_API_KEY
uv sync --extra dev
```

If your LangSmith account is in the EU region, set
`LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` in `.env` — otherwise
trace ingestion returns `403 Forbidden` (specs §8.0).

## Sanity check (stage 0-1)

Rebuild the mock database, print computed delivery facts, and issue one traced
LLM call through OpenRouter:

```bash
uv run python -m scripts.sanity_check
```

The offline part (database + facts) runs without any API key; the LLM hello
trace is skipped automatically when no key is configured.

## Running a claim (stage 4, human-in-the-loop)

Submit and review are two separate invocations; state persists across the pause
via a SQLite checkpointer, so review can happen later by `thread_id`.

```bash
# 1. File a complaint -> runs the graph up to the manager-review pause.
uv run python -m src.cli submit --text "Order ORD-10432 arrived 4 days late!"

# 2. Resume with the manager's decision (use the thread_id printed above).
uv run python -m src.cli review --thread <id> --decision approve
uv run python -m src.cli review --thread <id> --decision edit \
    --verdict not_justified --action-kind decline --comment "SLA met"
uv run python -m src.cli review --thread <id> --decision reject --comment "..."

# End-to-end demo over built-in complaints, auto-approving each:
uv run python -m src.cli demo
```

## Layout

| Path | Purpose |
|------|---------|
| `src/config.py` | env-driven settings, paths, per-node model ids |
| `src/llm.py` | OpenRouter chat-model factory |
| `src/structured.py` | JSON + Pydantic + retry structured-output helper |
| `src/schemas.py` | Pydantic output schemas for the LLM nodes |
| `src/prompts/` | node system prompts |
| `src/graph/` | state, nodes, and graph assembly (with HITL interrupt) |
| `src/db.py` | SQLite connection + `init_db` |
| `src/tools/` | order lookup and deterministic delivery-fact computation |
| `src/cli.py` | submit / review / demo commands |
| `src/feedback.py` | posts manager review outcomes to LangSmith as ground truth |
| `src/observability.py` | LangSmith tracing setup (EU endpoint) |
| `evals/` | golden dataset, target, evaluators, and the eval runner |
| `data/seed.sql` | schema + deterministic seed fixtures |
| `scripts/sanity_check.py` | stage 0-1 smoke test |
| `tests/` | offline tests for the deterministic fact logic |
| `docs/monitoring.md` | LangSmith dashboards & alerts runbook (stage 6) |

## Evaluation & feedback

```bash
# Offline evaluation over the golden dataset (creates it in LangSmith on first run):
RUN_DATE=2026-09-23 uv run python -m evals.run_eval
```

Manager decisions from `review` are posted back to the original judged trace as
feedback (`verdict_correct`, `action_correct`, `manager_verdict`,
`review_status`), forming the ground-truth loop described in
[docs/monitoring.md](docs/monitoring.md).
