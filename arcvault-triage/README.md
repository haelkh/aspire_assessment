# ArcVault Support Triage System

AI-powered intake and triage workflow for synthetic ArcVault support requests.
Built for the Valsoft AI Engineer assessment using free/open-source tooling.

## What This Implements

- Automatic ingestion via webhook (`POST /intake`)
- LLM classification into required categories and priority
- Confidence scoring with guarded parsing and fallback behavior
- Enrichment (core issue, identifiers, urgency signal, team-ready summary)
- Routing with `proposed_queue` and final `destination_queue`
- Escalation to a separate queue (`Human Review`) for low-confidence or rule-based cases
- Structured output to local JSON and optional Google Sheets
- Deterministic submission artifact generation for exactly 5 required samples

## Workflow

`Ingest -> Classify -> Enrich -> Route -> Output`

Escalation rules:

- confidence `< 0.70`
- keyword match (for example `outage`, `down for all users`, `multiple users affected`)
- billing amount delta `> $500` for `Billing Issue`

## Tech Stack

- Python 3.10+
- LangGraph
- Gemini API (`google-generativeai`)
- FastAPI (webhook ingestion)
- Gradio (demo UI)
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

### 3. Run

Gradio demo UI:

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

Intake example:

```bash
curl -X POST http://127.0.0.1:8000/intake \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"Email\",\"message\":\"Login fails with 403 for multiple users\"}"
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

- Timestamp
- Source
- Message
- Category
- Priority
- Confidence
- Core Issue
- Identifiers
- Urgency
- Proposed Queue
- Final Queue
- Escalation
- Escalation Rules
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

## License

Created for the Valsoft AI Engineer technical assessment.
