"""
Prompt templates for the ArcVault Triage workflow.

This module contains the prompts used for LLM-based classification
and enrichment of customer support messages.
"""

# === Classification Prompt ===
CLASSIFICATION_PROMPT = """You are a support ticket classifier for ArcVault, a B2B software company.

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

Return JSON in this exact format:
{{"category": "<category>", "priority": "<priority>", "confidence": <float>}}"""


# === Enrichment Prompt ===
ENRICHMENT_PROMPT = """You are extracting structured information from a support message for a B2B software company called ArcVault.

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

Return JSON in this exact format:
{{"core_issue": "<one sentence>", "identifiers": ["<id1>", "<id2>"], "urgency_signal": "<explanation or None>", "human_summary": "<2-3 sentences>"}}"""


# === Prompt Design Documentation ===
PROMPT_DESIGN_RATIONALE = {
    "classification": """
## Classification Prompt Design Rationale

### Why This Structure?
1. **Clear Category Definitions**: Each category has explicit examples to reduce ambiguity.
   This helps the model distinguish between similar categories (e.g., Bug Report vs Incident/Outage).

2. **JSON-Only Output**: By requiring "ONLY valid JSON with no additional text", we eliminate
   parsing issues. The model won't wrap output in markdown code blocks or add explanations.

3. **Confidence Scoring**: The explicit confidence scale (0.0-1.0 with examples) helps the model
   calibrate its uncertainty. This enables our escalation logic for low-confidence cases.

4. **Source Context**: Including the message source (Email, Web Form, Support Portal) provides
   context that can affect classification. For example, emails tend to be more formal.

### Tradeoffs Made
- **Simplicity vs Nuance**: Used 5 broad categories instead of 10+ specific ones. This reduces
  classification errors but may require human review for edge cases.
- **No Few-Shot Examples**: Chose not to include example classifications to save tokens and
  avoid biasing the model toward specific patterns. With more time, I'd add 2-3 examples.

### What I'd Change With More Time
1. Add 2-3 few-shot examples for each category
2. Implement a two-stage classification (first broad, then specific subcategory)
3. Add language detection for multilingual support
4. Include sentiment analysis in the classification step
""",
    "enrichment": """
## Enrichment Prompt Design Rationale

### Why This Structure?
1. **Separate from Classification**: Enrichment is a distinct step because:
   - Different cognitive task (extraction vs classification)
   - Can use classification results as context
   - Allows for different model or parameters if needed

2. **Structured Extraction**: The four fields (core_issue, identifiers, urgency_signal, human_summary)
   provide exactly what downstream teams need without overwhelming them.

3. **Identifier Extraction**: Explicitly listing what counts as an identifier helps the model
   find relevant information that could be used for automated lookups.

4. **Human-First Summary**: The human_summary is written for humans, not machines. This is what
   support teams will actually read, so it's prioritized.

### Tradeoffs Made
- **Word Limits**: Added max word counts to prevent verbose outputs that waste tokens and
  overwhelm readers. This trades detail for clarity.
- **Single core_issue**: Limited to one sentence to force focus. With more time, I'd allow
  a list of issues for complex messages.

### What I'd Change With More Time
1. Add entity recognition for dates, times, and monetary amounts
2. Implement multi-language support for international customers
3. Add suggested actions based on the issue type
4. Include customer sentiment score
5. Extract and validate any URLs or email addresses
"""
}
