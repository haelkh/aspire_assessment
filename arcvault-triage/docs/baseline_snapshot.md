# Baseline Snapshot: Problem State vs Implemented System

This document captures the "before and after" view of the ArcVault scenario from the assessment brief.

## 1. Baseline (Scenario Problem)

From the assessment prompt, the baseline process is:

- inbound requests arrive unstructured from email, web forms, and support portal
- messages are triaged manually by humans
- requests frequently land in the wrong operational queue
- no standardized confidence scoring or escalation policy
- downstream teams receive inconsistent context

## 2. Implemented State (This Submission)

### Workflow capabilities

1. Automatic ingestion via API/UI/CLI trigger paths
2. LLM-based classification with required fields:
   - category
   - priority
   - confidence
3. Structured enrichment:
   - core issue
   - identifiers
   - urgency signal
   - human-readable summary
4. Deterministic routing:
   - `proposed_queue`
   - `destination_queue`
5. Rule-based escalation to `Human Review`
6. Persisted structured outputs (JSONL + submission JSON + optional Sheets)

### Operational metadata added

- `record_id`
- `ingestion_id`
- `processing_ms`
- `pipeline_version`
- escalation evidence fields

## 3. Delta Summary

| Dimension | Baseline | Implemented |
|---|---|---|
| Intake | Manual and unstructured | API-driven, validated payloads |
| Classification | Human-only, inconsistent | LLM + strict schema validation |
| Routing | Manual and error-prone | Rule-based queue mapping and escalation |
| Escalation | Ad-hoc | Explicit threshold and keyword/billing rules |
| Output | Inconsistent notes | Structured JSON records with full context |
| Traceability | Limited | Rich metadata and reproducible artifacts |

## 4. Outcome on the Five Required Samples

Expected final pattern:

- four samples route to their domain queue (Engineering/Product/Billing/IT-Security)
- outage-like sample routes to `Human Review`

Detailed records are available in:

- `output/submission_records.json`
- `output/submission_summary.md`

## 5. Remaining Gaps (Known and Accepted for Assessment Scope)

1. No production-grade distributed queue or dead-letter handling.
2. In-memory API rate limiting (not centralized).
3. Cost and latency depend on external model quota conditions.
4. No long-term human feedback loop yet (planned for phase 2).
