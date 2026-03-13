# Prompt Documentation

This document explains the prompts used in the two LLM stages: classification and enrichment.
Each stage includes the full prompt, rationale, tradeoffs, and improvement ideas.

## Prompt 1 - Classification and Priority

### Prompt Text

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

Example 1 (Bug Report vs Incident/Outage — note the distinction):
MESSAGE SOURCE: Email
MESSAGE CONTENT: I can't access my dashboard since this morning. Getting a 500 error on every page.
{"category": "Bug Report", "priority": "High", "confidence": 0.85}
Rationale: Single user affected with a specific error code points to Bug Report, not Incident/Outage.

Example 2 (Incident/Outage — multiple users, service-level impact):
MESSAGE SOURCE: Support Portal
MESSAGE CONTENT: Our entire team is locked out of ArcVault. None of us can reach the login page. Started 30 min ago.
{"category": "Incident/Outage", "priority": "High", "confidence": 0.95}
Rationale: Multiple users, complete service unavailability, time-bounded onset = Incident/Outage.

Example 3 (Billing Issue — not a Feature Request even though they mention improvement):
MESSAGE SOURCE: Web Form
MESSAGE CONTENT: We were charged $2,100 this month but our plan is $1,500. Also, it would be nice to see a billing breakdown by department.
{"category": "Billing Issue", "priority": "High", "confidence": 0.80}
Rationale: Primary intent is disputing an overcharge. The feature suggestion is secondary.

### Now classify this message

Return JSON in this exact format:
{"category": "<category>", "priority": "<priority>", "confidence": <float>}
```

### Why It Is Structured This Way

This prompt uses a strict enum-style output and a hard JSON contract so routing logic can stay deterministic and parseable. It front-loads category definitions and priority criteria to reduce ambiguity on edge cases, and asks for calibrated confidence because confidence drives escalation decisions. The wording stays compact to reduce token cost while preserving enough context to separate similar labels such as `Bug Report` vs `Incident/Outage`.

**Few-shot examples** were added to resolve the most common ambiguity points: (1) single-user bug vs multi-user outage, (2) billing complaint with a secondary feature request, and (3) clarity on confidence calibration. Examples use realistic messages with brief rationale so the model understands the decision boundary, not just the answer.

**Structured output mode** (`response_mime_type="application/json"`) is used at the API level to guarantee valid JSON responses, eliminating the need for markdown-stripping or regex extraction in the common case. A fallback extraction path remains for compatibility.

### Tradeoffs

- We intentionally use fixed categories instead of open classification, which improves consistency but limits expressiveness.
- Few-shot examples are deliberately limited to 3 to keep token cost low while covering the most impactful ambiguity points.
- Confidence is self-reported by the model, so application-side guardrails are required (implemented in `workflow/nodes.py`).

### What I Would Improve With More Time

- Add subcategory prediction in a second pass.
- Add confidence calibration checks against historical outcomes.
- Add sentiment analysis for customer satisfaction signals.

## Prompt 2 - Enrichment and Summary

### Prompt Text

```text
You are extracting structured information from a support message for a B2B software company called ArcVault.

MESSAGE: {message}
CLASSIFICATION: {category} (Priority: {priority})

Extract the following information and return ONLY valid JSON with no additional text, no markdown formatting, just the raw JSON object.

1. core_issue: One clear sentence (max 20 words) summarizing the main problem or request
2. identifiers: A list of any relevant identifiers found in the message:
   - Account IDs or usernames
   - Invoice numbers
   - Error codes
   - URLs or paths
   - Reference numbers
   If no identifiers found, return an empty list []
3. urgency_signal: Briefly explain WHY this might be urgent, or "None" if not urgent
4. human_summary: 2-3 sentences (max 100 words total) that a support team member can read quickly

### Example

MESSAGE: We're seeing error code ERR_SYNC_FAIL on account acme-corp-99 when syncing audit logs. Started after your v3.2 release.
CLASSIFICATION: Bug Report (Priority: High)
{"core_issue": "Audit log sync fails with ERR_SYNC_FAIL after v3.2 release.", "identifiers": ["ERR_SYNC_FAIL", "acme-corp-99", "v3.2"], "urgency_signal": "Compliance-related feature broken after a release could affect audit readiness.", "human_summary": "Customer acme-corp-99 reports that audit log syncing fails with ERR_SYNC_FAIL since the v3.2 release. This may affect their compliance workflows. Engineering should investigate the sync pipeline for regressions introduced in v3.2."}

### Now extract from this message

Return JSON in this exact format:
{"core_issue": "<one sentence>", "identifiers": ["<id1>", "<id2>"], "urgency_signal": "<explanation or None>", "human_summary": "<2-3 sentences>"}
```

### Why It Is Structured This Way

This prompt is separated from classification to keep each model task focused: classification decides ownership and risk, enrichment extracts actionable context. The schema is intentionally minimal and practical for downstream teams, with one short issue sentence, explicit identifiers, an urgency hint, and a human-readable summary. The JSON-only requirement keeps it machine-safe, while the colleague-briefing style instruction keeps summaries useful in real support operations.

A single **few-shot example** demonstrates ideal extraction density — showing how to identify error codes, account IDs, and version references within a realistic message. This helps the model calibrate the level of detail expected, particularly for the `identifiers` field where under-extraction is common without examples.

### Tradeoffs

- The schema is lean and omits richer entities (for example dates and amounts) to keep complexity low.
- A single `core_issue` field can under-represent multi-problem messages.
- Summary quality depends on model consistency; fallback handling in code is used when parsing fails.

### What I Would Improve With More Time

- Add explicit extraction of monetary amounts, dates, and impacted-user counts.
- Add suggested next action field for the destination team.
- Add multilingual enrichment and optional translation support.

## Prompt/Code Alignment

- Prompt output contracts are validated and sanitized in `workflow/nodes.py`.
- **Structured output mode** at the API level guarantees valid JSON in the common case.
- **Retry with exponential backoff** handles transient API failures (3 attempts, 1s/2s/4s with jitter).
- Invalid enums or malformed JSON cannot break routing.
- Low-confidence or uncertain outputs are intentionally pushed into human review.
