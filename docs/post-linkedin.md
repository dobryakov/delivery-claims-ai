People often ask me to show an agentic-workflow example that's close to logistics and retail, not another toy chatbot. So I took a slice of a production system, adapted it, and stripped out the commercial data so I could share it.

The task: a customer complains that their order arrived late. The system classifies the complaint, extracts the order id from free text, looks up promised vs. actual delivery dates, and decides whether it's justified — then hands it to a manager to approve, edit, or reject before anything is finalized.

The whole thing is built on one principle: code owns the facts, the LLM owns the judgment.

Dates, delay in days, and the compensation ladder are computed in plain Python from the database. The model never recomputes a number. Its only job is the reasoning: is this justified, what should we offer, should we escalate. That split is what makes evaluation meaningful — you measure judgment, not arithmetic.

A few things worth stealing:

Human-in-the-loop is real, not a demo. The graph pauses on an interrupt, persists its full state to a checkpointer, and resumes days later from a separate process by thread id.

Structured output without blind trust. Cheap models are unreliable with strict JSON, so a parse-validate-retry helper guards every call. On failure the judge returns "insufficient data" rather than inventing a verdict.

Observability drives improvement. Every run is traced, and manager decisions post back to the judged trace as ground truth — so the disagreement rate is a live quality signal and the overrides become your next regression set, no extra labeling.

Stack: LangGraph for the workflow, LangSmith for tracing and evals, models routed through OpenRouter so any node is a one-line swap.

It's a trimmed-down slice, but the boundaries are drawn exactly where they are in the real system. Repo and a full engineering write-up in the comments.

#AI #LangGraph #LangSmith #LLM #AgenticAI #MLOps #Logistics #Retail #SoftwareEngineering
