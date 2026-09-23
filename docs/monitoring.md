# Online monitoring & alerts (specs §8.5)

This is a runbook for the LangSmith side of stage 6. Dashboards and alerts are
configured in the LangSmith UI (EU: `https://eu.smith.langchain.com`, project
`delivery-claims-ai`); nothing here needs code beyond the tracing and feedback
already emitted by the app.

## What the app already emits

- **Traces** — every graph run (submit and review), with node/LLM/tool spans,
  latency, and token/cost (specs §8.1).
- **Manager feedback** on the original judged trace (specs §8.2), posted by
  `src/feedback.py` in the `finalize` node:
  | key | type | meaning |
  |-----|------|---------|
  | `verdict_correct` | 0/1 | model verdict accepted without change |
  | `action_correct` | 0/1 | proposed action accepted without change |
  | `manager_verdict` | categorical | the manager's final verdict (ground truth) |
  | `review_status` | categorical | approved / edited / rejected |

The manager-vs-model disagreement rate is simply `1 - mean(verdict_correct)`.

## Dashboards to build

1. **Verdict distribution** — count of runs by model verdict; watch the share of
   `insufficient_data`.
2. **Manager agreement** — mean `verdict_correct` and `action_correct` over time;
   the core quality signal under variant B.
3. **Review outcomes** — breakdown of `review_status` (approved / edited /
   rejected).
4. **Latency & cost** — p50/p95 latency and cost per claim, split by model.

## Alerts to configure

- **Agreement drop** — alert when mean `verdict_correct` over the last N runs
  falls below a threshold (e.g. < 0.85, matching the §1.4 target).
- **Tool errors** — alert on a spike in errored `enrich` / DB tool spans.
- **Latency** — alert on p95 latency above a ceiling.
- **insufficient_data spike** — a sudden rise can indicate extraction or DB
  regressions upstream of the judge.

## The improvement loop (specs §8.6)

trace → manager feedback (`verdict_correct`, `manager_verdict`) → collect the
disagreements into a `claims_from_prod` dataset (specs §8.3) → re-run the
offline evaluators (`evals/run_eval.py`) on a new prompt/model version →
compare experiments in LangSmith before rolling out.

Online sampling: a fraction of production traces can be auto-scored by the
LLM-as-judge evaluators in the background to catch drift between manager reviews.
