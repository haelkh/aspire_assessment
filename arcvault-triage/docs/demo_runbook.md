# Demo Runbook (6-8 Minutes)

Use this script for a clean assessment recording. Each section includes narration cues.

## 0. Setup (before recording)

1. Activate environment and install deps.
2. Ensure `.env` has `GEMINI_API_KEY`.
3. Optional: configure Google Sheets credentials.
4. Delete `output/processed_records.json` for a clean run.

## 1. Start services (30 seconds)

### What to do

Terminal A — start webhook API:

```bash
uvicorn ingestion.webhook_api:app --host 127.0.0.1 --port 8000
```

Terminal B — start Gradio UI:

```bash
python app.py
```

### What to say

> "I've built three ingestion modes: a FastAPI webhook that auto-triggers on POST, a Gradio web UI for interactive use, and a CLI for batch processing. Let me start both services."

## 2. Show ingestion trigger (45 seconds)

### What to do

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Post one intake payload:

```bash
curl -X POST http://127.0.0.1:8000/intake -H "Content-Type: application/json" -d "{\"source\":\"Email\",\"message\":\"Dashboard is down for all users since 2pm\"}"
```

### What to say

> "This demonstrates Step 1 — automatic ingestion. When a message hits POST /intake, the full pipeline runs: classification, enrichment, routing, and output — all in one call. The endpoint also has rate limiting for production safety."

> "Notice in the response: the message was classified as Incident/Outage with High priority, and because it contains 'down for all users', it triggered keyword-based escalation and was routed to Human Review instead of Engineering."

## 3. Process all 5 required samples (2-3 minutes)

### What to do

Use CLI:

```bash
python main.py all
```

Or use the Gradio UI — click "Process All Samples" button.

### What to say (walk through each result)

> "Now I'll process all five required samples. For each one, note four things:"

> "First — the classification fields: category, priority, and confidence score. The LLM uses few-shot examples to distinguish between similar categories like Bug Report versus Incident/Outage."

> "Second — the enrichment fields: a one-sentence core issue, extracted identifiers like error codes and invoice numbers, an urgency signal, and a 2-3 sentence human-readable summary."

> "Third — the routing fields: proposed_queue shows which team should own this based on category, and destination_queue shows where it actually goes. For escalated records, destination is Human Review."

> "Fourth — escalation behavior: confidence below 70%, keyword matches, or billing deltas over $500 all trigger escalation. The rules that fired are recorded in machine-readable format for auditing."

## 4. Generate deterministic deliverables (45 seconds)

### What to do

```bash
python main.py all --submission
```

Open and show `output/submission_records.json` and `output/submission_summary.md`.

### What to say

> "This generates the canonical submission artifacts — exactly 5 records, sorted by sample ID, with every required field. The summary file gives a quick overview of category, confidence, routing, and escalation status for each sample."

## 5. Brief architecture explanation (1-2 minutes)

### What to say

> "The system is built on LangGraph, which gives us typed state management and conditional branching. The pipeline flows: Classify → Enrich → Route, then branches to either Output or Escalate based on the escalation flag."

> "A key design choice is separating proposed_queue from destination_queue. When a message is escalated, we still record which team should eventually own it — the human reviewer can see that context."

> "The Gemini client uses structured output mode with response_mime_type='application/json' to guarantee valid JSON, plus retry with exponential backoff for resilience. Models outputs are also validated with guardrails — invalid categories get coerced to defaults, and any validation failure forces confidence to 0.0 to trigger safe escalation."

> "For production, I would add a dead-letter queue for failed records, persistent deduplication via Redis, API authentication on the webhook, and a feedback loop where humans can correct labels to tune prompts over time."

## 6. Close with docs (30 seconds)

### What to say

> "All documentation is in the repo: the architecture write-up with Mermaid diagrams, prompt documentation explaining rationale and tradeoffs for each LLM step, and a traceability matrix mapping every assessment requirement to code and evidence."

Point to:

1. `docs/architecture_writeup.md`
2. `prompts/prompt_documentation.md`
3. `docs/assessment_traceability.md`
