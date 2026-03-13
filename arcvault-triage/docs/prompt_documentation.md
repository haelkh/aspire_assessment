# ArcVault Prompt Documentation

This document covers all LLM prompts used by the workflow and explains why each prompt is structured the way it is, what tradeoffs were made, and what would change in a future iteration.

## 1. Prompt Scope and Model Setup

### LLM steps

1. Classification (`category`, `priority`, `confidence`)
2. Enrichment (`core_issue`, `identifiers`, `urgency_signal`, `human_summary`)

### Current model configuration

- Primary model: `GEMINI_MODEL` (default `gemini-2.5-flash-lite`)
- Fallback chain: `GEMINI_FALLBACK_MODELS` (default includes `gemini-2.5-flash`, `gemini-2.0-flash`)
- Structured response mode: `response_mime_type="application/json"`
- Retry/backoff: configurable via `GEMINI_MAX_RETRIES`, `GEMINI_BASE_DELAY_SECONDS`, `GEMINI_MAX_JITTER_SECONDS`

## 2. Prompt A: Classification

### Prompt text (from `workflow/prompts.py`)

```text
You are a support ticket classifier for ArcVault, a B2B software company.

Analyze the following message and classify it. Return ONLY valid JSON with no additional text, no markdown formatting, just the raw JSON object.

MESSAGE SOURCE: {source}
MESSAGE CONTENT: {message}

Classify into exactly ONE category:
- Bug Report: Technical issues, errors, broken functionality, system not working as expected
- Feature Request: Requests for new features, enhancements, or improvements
- Billing Issue: Payment problems, invoice discrepancies, subscription questions
- Technical Question: How-to questions, configuration help, setup assistance
- Incident/Outage: System down, widespread issues affecting multiple users, service unavailable

Assign priority:
- High: System down, billing errors over $500, security issues, multiple users affected, production impact
- Medium: Feature requests, non-critical bugs, account issues, configuration questions
- Low: General questions, minor enhancement suggestions, documentation requests

Assign confidence:
- A float between 0.0 and 1.0 representing how certain you are about this classification
- 1.0 = Very confident, clear-cut case
- 0.5 = Moderate confidence, could go either way
- 0.0 = Very uncertain, need human review

### Examples

Example 1 (Bug Report vs Incident/Outage - note the distinction):
MESSAGE SOURCE: Email
MESSAGE CONTENT: I can't access my dashboard since this morning. Getting a 500 error on every page.
{"category": "Bug Report", "priority": "High", "confidence": 0.85}
Rationale: Single user affected with a specific error code points to Bug Report, not Incident/Outage.

Example 2 (Incident/Outage - multiple users, service-level impact):
MESSAGE SOURCE: Support Portal
MESSAGE CONTENT: Our entire team is locked out of ArcVault. None of us can reach the login page. Started 30 min ago.
{"category": "Incident/Outage", "priority": "High", "confidence": 0.95}
Rationale: Multiple users, complete service unavailability, time-bounded onset = Incident/Outage.

Example 3 (Billing Issue - not a Feature Request even though they mention improvement):
MESSAGE SOURCE: Web Form
MESSAGE CONTENT: We were charged $2,100 this month but our plan is $1,500. Also, it would be nice to see a billing breakdown by department.
{"category": "Billing Issue", "priority": "High", "confidence": 0.80}
Rationale: Primary intent is disputing an overcharge. The feature suggestion is secondary.

### Now classify this message

Return JSON in this exact format:
{"category": "<category>", "priority": "<priority>", "confidence": <float>}
```

### Why this structure

The prompt is designed to produce deterministic downstream routing inputs. Fixed category and priority enums minimize variance and simplify validation. The confidence field exists specifically because escalation policy depends on uncertainty (`confidence < 0.70`).

Few-shot examples are focused on known confusion cases:

- single-user bug versus multi-user outage
- billing dispute mixed with feature language

This avoids overfitting to generic examples while keeping prompt token cost controlled.

### Tradeoffs

- Strict enums improve consistency but reduce expressiveness.
- Confidence is model self-reporting and can drift without calibration.
- A single-pass classifier can still struggle with mixed-intent messages.

### What I would change with more time

- Add a second-pass verifier prompt for borderline classifications.
- Add a light calibration layer using historical confusion pairs.
- Add optional intent-splitting for truly multi-topic tickets.

## 3. Prompt B: Enrichment

### Prompt text (from `workflow/prompts.py`)

```text
You are extracting structured information from a support message for a B2B software company called ArcVault.

MESSAGE: {message}
CLASSIFICATION: {category} (Priority: {priority})

Extract the following information and return ONLY valid JSON with no additional text, no markdown formatting, just the raw JSON object.

1. core_issue: One clear sentence (max 20 words) summarizing the main problem or request
2. identifiers: A list of any relevant identifiers found in the message:
   - Account IDs or usernames (e.g., "jsmith", "user123")
   - Invoice numbers (e.g., "#8821", "INV-12345")
   - Error codes (e.g., "403", "500", "ERR_TIMEOUT")
   - URLs or paths (e.g., "arcvault.io/user/jsmith")
   - Reference numbers
   If no identifiers found, return an empty list []
3. urgency_signal: Briefly explain WHY this might be urgent, or "None" if not urgent
   - Consider: business impact, user impact, time sensitivity, financial impact
4. human_summary: 2-3 sentences (max 100 words total) that a support team member can read to quickly understand:
   - What the customer needs
   - What context they provided
   - What action might be needed
   Write this as if you're briefing a colleague who will handle this ticket.

### Example

MESSAGE: We're seeing error code ERR_SYNC_FAIL on account acme-corp-99 when syncing audit logs. Started after your v3.2 release.
CLASSIFICATION: Bug Report (Priority: High)
{"core_issue": "Audit log sync fails with ERR_SYNC_FAIL after v3.2 release.", "identifiers": ["ERR_SYNC_FAIL", "acme-corp-99", "v3.2"], "urgency_signal": "Compliance-related feature broken after a release could affect audit readiness.", "human_summary": "Customer acme-corp-99 reports that audit log syncing fails with ERR_SYNC_FAIL since the v3.2 release. This may affect their compliance workflows. Engineering should investigate the sync pipeline for regressions introduced in v3.2."}

### Now extract from this message

Return JSON in this exact format:
{"core_issue": "<one sentence>", "identifiers": ["<id1>", "<id2>"], "urgency_signal": "<explanation or None>", "human_summary": "<2-3 sentences>"}
```

### Why this structure

The enrichment prompt is optimized for operational handoff quality. It separates extraction from classification so routing remains stable while enrichment can evolve independently. The fields were chosen to be immediately useful to receiving teams: concise issue statement, explicit identifiers, urgency rationale, and a readable summary.

### Tradeoffs

- Schema intentionally omits richer fields like dates, amounts, and affected-user counts.
- Enrichment quality is dependent on upstream classification context.
- Summary quality can vary; guardrail fallback text prevents hard failure.

### What I would change with more time

- Add explicit extraction for amounts, timestamps, and impacted users.
- Add `recommended_next_action` and `required_owner_inputs` fields.
- Add language-detection and optional translation for global support channels.

## 4. Guardrails and Prompt Safety

- Classification output is validated against strict category/priority enums and confidence range.
- Invalid classification output raises a hard error to avoid silent misrouting.
- Enrichment failures fall back to safe defaults to keep processing operational.
- Routing escalation is rule-based, not prompt-only, to keep human-review triggers deterministic.

## 5. Prompt Versioning Notes

Prompt text lives in `workflow/prompts.py` and this document is the human-readable rationale.
When prompt changes are made, both files should be updated together and tested against the five canonical sample inputs in `config/sample_inputs.json`.
