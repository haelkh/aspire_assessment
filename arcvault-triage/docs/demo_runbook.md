# Demo Runbook (6-8 Minutes)

Use this script for a clean assessment recording.

## 0. Setup (before recording)

1. Activate environment and install deps.
2. Ensure `.env` has `GEMINI_API_KEY`.
3. Optional: configure Google Sheets credentials.

## 1. Start services (30 seconds)

1. Terminal A:
```bash
uvicorn ingestion.webhook_api:app --host 127.0.0.1 --port 8000
```
2. Terminal B:
```bash
python app.py
```

## 2. Show health and ingestion trigger (45 seconds)

1. Health check:
```bash
curl http://127.0.0.1:8000/health
```
2. Post one intake payload:
```bash
curl -X POST http://127.0.0.1:8000/intake -H "Content-Type: application/json" -d "{\"source\":\"Email\",\"message\":\"Dashboard is down for all users\"}"
```
3. Call out that this satisfies automatic workflow start.

## 3. Process all 5 required samples (2-3 minutes)

Use UI batch button or CLI:

```bash
python main.py all
```

Narration points:

1. Classification fields (`category`, `priority`, `confidence`).
2. Enrichment fields (`core_issue`, `identifiers`, `urgency_signal`, `human_summary`).
3. Routing fields (`proposed_queue` vs final `destination_queue`).
4. Escalation behavior (`escalation_flag`, `escalation_rules_triggered`).

## 4. Generate deterministic deliverables (45 seconds)

```bash
python main.py all --submission
```

Show:

1. `output/submission_records.json`
2. `output/submission_summary.md`

## 5. Brief architecture explanation (1-2 minutes)

1. LangGraph node flow.
2. Why escalation routes to separate queue.
3. How low-confidence and billing-delta rules prevent unsafe automation.
4. Production upgrades you would add next.

## 6. Close with docs (30 seconds)

Reference:

1. `docs/architecture_writeup.md`
2. `prompts/prompt_documentation.md`
3. `docs/assessment_traceability.md`

This keeps the demo concise, complete, and aligned to rubric language.
