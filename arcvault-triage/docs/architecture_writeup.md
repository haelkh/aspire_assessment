# ArcVault AI Intake and Triage - Architecture Write-Up

## Executive Summary

This system automates ArcVault customer request intake, classification, enrichment, routing, and escalation using a LangGraph workflow with Gemini-based LLM steps.

The workflow accepts unstructured requests from multiple channels, produces machine-usable structured records, and sends each item either to its operational queue or to a human review queue when risk criteria are met.

## 1. System Design

### 1.1 End-to-end flow

`Ingest -> Classify -> Enrich -> Route -> Output`

- Ingestion starts automatically from API/UI/CLI triggers.
- Classification returns `category`, `priority`, `confidence`.
- Enrichment returns `core_issue`, `identifiers`, `urgency_signal`, `human_summary`.
- Routing decides `proposed_queue`, `destination_queue`, and escalation fields.
- Output persists a structured record to JSONL and optionally offloads to Google Sheets.

### 1.2 Components and responsibilities

| Component | File(s) | Responsibility |
|---|---|---|
| Intake API | `ingestion/webhook_api.py` | Receives inbound requests, validates payload, rate-limits, starts processing |
| Web Console API | `app.py`, `web/` | Interactive demo UI, single-run and batch processing |
| Orchestration | `workflow/graph.py` | Defines state graph and conditional route to normal vs escalated output |
| LLM Integration | `integrations/gemini_client.py` | Gemini call abstraction, retries/backoff, fallback model switching |
| Prompt Templates | `workflow/prompts.py` | Classification and enrichment instructions |
| Business Rules | `workflow/nodes.py`, `config/settings.py` | Validation, queue mapping, escalation rules, persistence payload |
| Persistence | `storage/record_store.py`, `integrations/sheets_client.py` | Local JSONL records + optional Google Sheets rows |

### 1.3 State and data contract

The shared workflow state (`workflow/state.py`) carries:

- Input metadata: `source`, `request_id`, `customer_id`, `received_at`, `channel_metadata`
- Model outputs: `category`, `priority`, `confidence`, `classification_model`, `enrichment_model`
- Enrichment fields: `core_issue`, `identifiers`, `urgency_signal`, `human_summary`
- Routing fields: `proposed_queue`, `destination_queue`, `escalation_flag`, escalation evidence
- Operational trace fields: `ingestion_id`, `record_id`, `processing_ms`, `pipeline_version`

## 2. Routing Logic

### 2.1 Queue mapping

| Category | Proposed Queue |
|---|---|
| Bug Report | Engineering |
| Feature Request | Product |
| Billing Issue | Billing |
| Technical Question | IT/Security |
| Incident/Outage | Engineering |

### 2.2 Decision policy

1. Determine `proposed_queue` from category.
2. Evaluate escalation criteria.
3. If escalated, set `destination_queue = Human Review`.
4. Otherwise, set `destination_queue = proposed_queue`.

This dual-queue design preserves intended owner while enforcing safer handling for risky or ambiguous cases.

## 3. Escalation Logic

Escalation is triggered if any condition is true:

1. `confidence < 0.70`
2. message contains escalation keywords (for example `outage`, `down for all users`, `multiple users affected`)
3. `Billing Issue` with at least two dollar amounts and `max-min > 500`
4. `Billing Issue` with one amount plus dispute language (for example `overcharge`, `billing error`)

For every escalation, the system stores:

- `escalation_rules_triggered` (machine-readable rule IDs)
- `escalation_rule_evidence` (human-readable evidence snippets)
- `escalation_reason` (explainable summary string)

## 4. Prompting and Model Strategy

- Primary model: configured by `GEMINI_MODEL` (current default: `gemini-2.5-flash-lite`)
- Fallbacks: `GEMINI_FALLBACK_MODELS` (default chain includes `gemini-2.5-flash`, `gemini-2.0-flash`)
- Retry policy: controlled by `GEMINI_MAX_RETRIES`, `GEMINI_BASE_DELAY_SECONDS`, `GEMINI_MAX_JITTER_SECONDS`

Guardrails fail classification loudly if enums/confidence are invalid, preventing silent misrouting.
Enrichment failures degrade gracefully with safe fallback text.

## 5. Structured Output Design

Each processed item becomes a JSON record with:

- Classification: category, priority, confidence
- Enrichment: core issue, identifiers, urgency signal, summary
- Routing: proposed queue, destination queue, escalation fields
- Operations: processing time, ingestion ID, record ID, pipeline version

Primary sink:

- `output/processed_records.jsonl` (append-only runtime log)

Submission sink:

- `output/submission_records.json` (deterministic 5-sample artifact)

Optional sink:

- Google Sheets (`integrations/sheets_client.py`)

## 6. Reliability, Cost, and Latency

### Reliability choices

- Strict schema validation on model outputs
- Retry with backoff and fallback models
- Non-blocking background Sheets writes for API requests
- Append-only local output to avoid whole-file rewrite failures

### Cost and latency tradeoffs

- Low-temperature JSON mode improves consistency but adds model latency
- Retries improve success rate but can increase request duration under quota/rate pressure
- Backoff parameters are now configurable to tune speed vs resilience by environment

## 7. Production-scale Improvements

If promoted beyond assessment scope:

1. Move intake rate-limiting to shared infrastructure (Redis/API gateway).
2. Add dead-letter workflow and replay tooling for failed records.
3. Add telemetry dashboards for latency, escalation rate, and model error rate.
4. Add prompt/version registry and A/B testing for model behavior.
5. Add signed webhook verification and secret rotation policy.

## 8. Phase 2 Plan (One Additional Week)

1. Human feedback loop for corrected labels and rule tuning.
2. Subcategory taxonomy and SLA-based prioritization.
3. Native downstream connectors (ticket creation by queue).
4. Automatic quality report on classification confidence and drift.
5. Incident-mode fast path for known outage patterns.
