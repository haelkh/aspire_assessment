# ArcVault Support Triage System

AI-powered intake and triage workflow for synthetic ArcVault support requests.
Built for the Valsoft AI Engineer assessment using free/open-source tooling.

## What This Implements

- Automatic ingestion via webhook (`POST /intake`) with rate limiting
- Optional webhook authentication (`X-API-Key`) when `INTAKE_API_KEY` is configured
- LLM classification into required categories and priority (with few-shot examples)
- Confidence scoring with strict guardrail validation and explicit classification errors
- Confidence metadata on successful classifications (`confidence_level`, `confidence_source`)
- Enrichment (core issue, identifiers, urgency signal, team-ready summary)
- Routing with `proposed_queue` and final `destination_queue`
- Escalation to a separate queue (`Human Review`) for low-confidence or rule-based cases
- Structured output to local JSONL + optional Google Sheets
- Persistent idempotency (SQLite) keyed by `request_id` or normalized message hash
- Correlation metadata in records (`ingestion_id`, `processing_ms`, `pipeline_version`)
- Deterministic submission artifact generation for exactly 5 required samples

## Workflow

`Ingest -> Classify -> Enrich -> Route -> Output`

Escalation rules:

- confidence `< 0.70`
- keyword match (for example `outage`, `down for all users`, `multiple users affected`)
- billing amount delta `> $500` for `Billing Issue`
- billing single-amount dispute language (for example `overcharge`, `billing error`) for `Billing Issue`

## Design Decisions

| Decision | Rationale |
|---|---|
| **LangGraph** over raw Python | Provides typed state management, conditional branching, and a visual graph structure that maps directly to the pipeline steps. Makes it easy to add/reorder nodes without refactoring control flow. |
| **`proposed_queue` + `destination_queue`** | Separates classification intent from final routing. Escalated records still show which team *should* own them (`proposed_queue`), while `destination_queue` reflects that they need human review first. |
| **Escalation rule composition** | Multiple independent rules (confidence, keywords, billing delta) are evaluated and accumulated. All triggered rules are recorded in machine-readable and human-readable formats for audit and debugging. |
| **Word-boundary keyword matching** | Uses `\b` regex boundaries instead of substring `in` to prevent false positives (e.g., "I'm down for that" matching "down"). |
| **Gemini structured output mode** | `response_mime_type="application/json"` increases JSON reliability, with strict guardrails that surface model failures instead of silently coercing invalid output. |
| **Retry with exponential backoff** | 3 attempts with 1s/2s/4s delays + jitter for resilience against transient Gemini API failures. |
| **Persistent idempotency** | SQLite-backed deduplication survives restarts and prioritizes caller-provided `request_id` when available. |
| **Append-safe output** | Runtime records are persisted as JSONL (`output/processed_records.jsonl`) to avoid read-modify-write race risks. |
| **Trace metadata** | Every run includes `ingestion_id`, `processing_ms`, and `pipeline_version` for easier diagnosis and demos. |

## Tech Stack

- Python 3.10+
- LangGraph
- Gemini API (`google-generativeai`)
- FastAPI (webhook ingestion)
- Native HTML/CSS/JS UI served by FastAPI
- Google Sheets (`gspread`) optional

## Quick Start

### 1. Install

```bash
cd arcvault-triage
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env
```

Set at least:

- `GEMINI_API_KEY=...`

Optional:

- `GOOGLE_SHEETS_SPREADSHEET_ID=...`
- `GOOGLE_CREDENTIALS_PATH=credentials/service_account.json`
- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `INTAKE_API_KEY=...` (enforces `X-API-Key` on `POST /intake`)
- `OUTPUT_JSONL_PATH=output/processed_records.jsonl`
- `IDEMPOTENCY_DB_PATH=output/triage_state.db`
- `PIPELINE_VERSION=1.1.0`

### 3. Run

Native web UI:

```bash
python app.py
```

CLI all samples:

```bash
python main.py all
```

CLI one sample:

```bash
python main.py sample 1
```

Webhook ingestion API:

```bash
uvicorn ingestion.webhook_api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Intake example (open endpoint mode):

```bash
curl -X POST http://127.0.0.1:8000/intake \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"Email\",\"message\":\"Login fails with 403 for multiple users\",\"request_id\":\"REQ-1001\",\"customer_id\":\"cust-acme\"}"
```

Intake example (API key enforced):

```bash
curl -X POST http://127.0.0.1:8000/intake \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $INTAKE_API_KEY" \
  -d "{\"source\":\"Email\",\"message\":\"Login fails with 403 for multiple users\",\"request_id\":\"REQ-1001\"}"
```

## Deterministic Submission Artifacts

Generate the canonical deliverables from exactly the 5 required samples:

```bash
python scripts/generate_submission_artifacts.py
```

Or through CLI:

```bash
python main.py all --submission
```

Generated files:

- `output/submission_records.json`
- `output/submission_summary.md`
- Runtime append log: `output/processed_records.jsonl`
- Idempotency DB: `output/triage_state.db`

## Testing

Run deterministic tests:

```bash
python -m pytest -q
```

Optional live smoke test (uses real API key):

```bash
python scripts/smoke_live_api.py
```

## Google Sheets (Optional)

If configured, each record is also appended to Sheets.
Recommended headers:

- Record ID
- Ingestion ID
- Pipeline Version
- Processing (ms)
- Replay
- Request ID
- Customer ID
- Received At
- Timestamp
- Source
- Message
- Category
- Priority
- Confidence
- Confidence Level
- Confidence Source
- Guardrail Flags
- Core Issue
- Identifiers
- Urgency
- Proposed Queue
- Final Queue
- Escalation
- Escalation Rules
- Escalation Evidence
- Escalation Reason
- Summary

## Project Structure

```text
arcvault-triage/
  app.py
  main.py
  ingestion/
    webhook_api.py
  workflow/
    state.py
    nodes.py
    graph.py
    prompts.py
  integrations/
    gemini_client.py
    sheets_client.py
  config/
    settings.py
    sample_inputs.json
  storage/
    idempotency_store.py
    record_store.py
  scripts/
    generate_submission_artifacts.py
    smoke_live_api.py
  tests/
  docs/
  prompts/
  output/
```

## Assessment Deliverables in Repo

- Architecture write-up: `docs/architecture_writeup.md`
- Prompt documentation: `prompts/prompt_documentation.md`
- Requirement traceability: `docs/assessment_traceability.md`
- Demo runbook: `docs/demo_runbook.md`
- Baseline snapshot (before/after reference): `docs/baseline_snapshot.md`

## License

Created for the Valsoft AI Engineer technical assessment.
