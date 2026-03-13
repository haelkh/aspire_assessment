# Demo Runbook (6-8 Minutes)

Use this script for a clean assessment recording. Each section includes narration cues.

## 0. Setup (before recording)

1. Activate environment and install dependencies.
2. Ensure `.env` has `GEMINI_API_KEY`.
3. Optional: set `INTAKE_API_KEY` to demo authenticated ingestion.
4. Optional: configure Google Sheets credentials.
5. Delete `output/processed_records.jsonl` and `output/triage_state.db` for a clean run.

## 1. Start services (30 seconds)

### What to do

Terminal A: start webhook API:

```bash
uvicorn ingestion.webhook_api:app --host 127.0.0.1 --port 8000
```

Terminal B: start native web UI:

```bash
python app.py
```

### What to say

> "I built three ingestion modes: a FastAPI webhook that auto-triggers on POST, a native web UI for interactive use, and a CLI for batch processing."

## 2. Show ingestion trigger (60 seconds)

### What to do

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Post one intake payload (open mode):

```bash
curl -X POST http://127.0.0.1:8000/intake -H "Content-Type: application/json" -d "{\"source\":\"Email\",\"message\":\"Dashboard is down for all users since 2pm\",\"request_id\":\"REQ-1001\",\"customer_id\":\"cust-acme\"}"
```

If `INTAKE_API_KEY` is set, show auth enforcement:

```bash
curl -X POST http://127.0.0.1:8000/intake -H "Content-Type: application/json" -H "X-API-Key: $INTAKE_API_KEY" -d "{\"source\":\"Email\",\"message\":\"Dashboard is down for all users since 2pm\",\"request_id\":\"REQ-1001\"}"
```

### What to say

> "This demonstrates Step 1 automatic ingestion. A new intake payload immediately runs classification, enrichment, routing, and persistence."

> "The endpoint now validates richer intake metadata, supports optional API-key protection, and emits trace fields like ingestion_id and processing_ms."

## 3. Process all 5 required samples (2-3 minutes)

### What to do

Use CLI:

```bash
python main.py all
```

Or use the web UI and click "Run Batch (All Samples)".

### What to say (walk through each result)

> "For each sample, verify classification fields, enrichment fields, routing fields, and escalation metadata."

> "Escalation now includes both machine-readable rule IDs and human-readable rule evidence."

## 4. Generate deterministic deliverables (45 seconds)

### What to do

```bash
python main.py all --submission
```

Open and show:

1. `output/submission_records.json`
2. `output/submission_summary.md`
3. `output/processed_records.jsonl` (runtime append log)

### What to say

> "This produces canonical artifacts for the 5 required samples and a runtime JSONL log for operational traceability."

## 5. Brief architecture explanation (1-2 minutes)

### What to say

> "The LangGraph pipeline is Classify -> Enrich -> Route, then Output or Escalate based on escalation_flag."

> "I separate proposed_queue from destination_queue so escalation can override final dispatch while preserving intended ownership."

> "For reliability, idempotency is now SQLite-backed, persistence is append-safe JSONL, and guardrail flags are surfaced in output."

> "For ingestion hardening, the webhook supports optional API key enforcement and richer validated payload metadata."

## 6. Close with docs (30 seconds)

### What to say

> "Documentation includes architecture, prompt rationale, and requirement traceability with before-vs-after improvements."

Point to:

1. `docs/architecture_writeup.md`
2. `prompts/prompt_documentation.md`
3. `docs/assessment_traceability.md`
