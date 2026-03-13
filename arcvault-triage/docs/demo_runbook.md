# ArcVault Demo Runbook

This runbook is designed for assessment demonstration and interview walkthrough.
It covers local setup, execution paths, and expected evidence artifacts.

## 1. Prerequisites

1. Python 3.10+
2. Dependencies installed:
   - `pip install -r requirements.txt`
3. Environment configured in `.env`:
   - `GEMINI_API_KEY`
   - optional: `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_CREDENTIALS_PATH`

## 2. Start the System

### Option A: Web Console (recommended for live demo)

```bash
cd arcvault-triage
python app.py
```

Open `http://127.0.0.1:7860`.

### Option B: Intake API

```bash
cd arcvault-triage
uvicorn ingestion.webhook_api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 3. Run the Five Required Samples

### Console path

1. Open the Intake tab.
2. Select sample 1 through sample 5.
3. Submit each one and capture:
   - category
   - priority
   - confidence
   - proposed queue
   - final queue
   - escalation reason (when present)

### CLI path

```bash
cd arcvault-triage
python main.py all --submission
```

This generates deterministic artifacts for all five required inputs.

## 4. Expected Results (High-level)

| Sample | Expected category | Expected destination behavior |
|---|---|---|
| 1 | Bug Report | Engineering |
| 2 | Feature Request | Product |
| 3 | Billing Issue | Billing (or Human Review if escalation rule triggers) |
| 4 | Technical Question | IT/Security |
| 5 | Incident/Outage | Human Review due to outage-style escalation signal |

## 5. Evidence to Capture

Minimum evidence for submission:

1. Workflow execution proof:
   - UI/API run showing all five samples processed
2. Structured output artifact:
   - `output/submission_records.json`
3. Summary artifact:
   - `output/submission_summary.md`
4. Docs:
   - `docs/architecture_writeup.md`
   - `docs/prompt_documentation.md`
   - `docs/assessment_traceability.md`

## 6. Recommended Live Interview Script (5-8 minutes)

1. Show the workflow diagram and queue mapping.
2. Process sample 1 and sample 5 to show normal path and escalation path.
3. Open generated JSON output and highlight required fields.
4. Explain two design tradeoffs:
   - strict guardrails versus model flexibility
   - background Sheets writes versus synchronous latency
5. Close with production scale improvements and phase-2 plan.

## 7. Troubleshooting

### Slow responses

Likely cause: LLM retries/backoff during API quota/rate pressure.

Tune in `.env`:

- `GEMINI_MAX_RETRIES=1`
- `GEMINI_BASE_DELAY_SECONDS=0.2`

### No rows in Google Sheets

1. Confirm spreadsheet ID and credentials path in `.env`.
2. Confirm you are checking `Sheet1` of the configured spreadsheet.
3. Wait 1-3 seconds for background offload in API flows.
4. Use a fresh `request_id` when replay behavior is enabled.
