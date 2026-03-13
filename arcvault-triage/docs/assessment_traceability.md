# ArcVault Assessment Traceability Matrix

This matrix maps each explicit requirement from `AI_Engineer_Technical_Intermediate-Senior.docx` to concrete implementation evidence in this repository.

## 1. Required Workflow Steps (Section 3.1)

| Requirement | Implementation | Evidence |
|---|---|---|
| Step 1 - Ingestion: workflow starts automatically on new input | FastAPI intake endpoint, web UI trigger, CLI trigger | `ingestion/webhook_api.py`, `app.py`, `main.py` |
| Step 2 - Classification with category, priority, confidence | `classify_node` calls Gemini prompt and validates output | `workflow/nodes.py`, `workflow/prompts.py` |
| Step 3 - Enrichment with core issue, identifiers, urgency | `enrich_node` extracts structured fields and summary | `workflow/nodes.py`, `workflow/prompts.py` |
| Step 4 - Routing to at least 3 queues + fallback | Queue mapping + escalation override to `Human Review` | `config/settings.py`, `workflow/nodes.py` |
| Step 5 - Structured output persisted | JSON records written to local JSONL and optional Sheets | `storage/record_store.py`, `integrations/sheets_client.py`, `output/submission_records.json` |
| Step 6 - Human escalation if low confidence or criteria match | Confidence threshold + keyword + billing rules | `workflow/nodes.py`, `config/settings.py` |

## 2. Output Field Compliance (Section 4.2)

Required visibility: category, priority, confidence score, entities, routing destination, escalation flag, summary.

All required fields are present in submission outputs:

- `output/submission_records.json`
- `output/submission_summary.md`

Key fields present per record:

- `category`
- `priority`
- `confidence`
- `core_issue`
- `identifiers`
- `urgency_signal`
- `proposed_queue`
- `destination_queue`
- `escalation_flag`
- `escalation_rules_triggered`
- `escalation_reason`
- `human_summary`

## 3. Deliverable Compliance (Section 4)

| Deliverable | Status | Evidence |
|---|---|---|
| 4.1 Working workflow demonstration | Implemented and runnable locally | `docs/demo_runbook.md`, `app.py`, `ingestion/webhook_api.py` |
| 4.2 Structured output file (5 samples) | Completed | `output/submission_records.json` |
| 4.3 Prompt documentation + rationale/tradeoffs | Completed | `docs/prompt_documentation.md` |
| 4.4 Architecture write-up (design, routing, escalation, scale, phase 2) | Completed | `docs/architecture_writeup.md` |

## 4. Sample Input Coverage (Section 2.1)

The five required synthetic inputs are represented in:

- `config/sample_inputs.json`

Deterministic artifact generation for those five records:

- `scripts/generate_submission_artifacts.py`

## 5. Evaluation Criteria Alignment (Section 5)

| Evaluation Dimension | How this submission addresses it |
|---|---|
| Workflow Functionality (25%) | End-to-end graph with intake, classify, enrich, route, output, escalation |
| Classification and Prompt Quality (25%) | Prompt templates + guardrail validation + JSON mode |
| System Design Thinking (20%) | Explicit architecture and decision rationale in `docs/architecture_writeup.md` |
| Structured Output Quality (15%) | Deterministic JSON output with complete routing and escalation metadata |
| Documentation and Communication (15%) | Runbook, architecture write-up, prompt documentation, traceability matrix |

## 6. Open Manual Submission Items

The assessment also asks for one demonstration format (recording/link/live demo). This is intentionally external to source code and should be added before final submission email:

1. Loom/video link or recorded walkthrough.
2. If needed, screenshots of each processing stage.
