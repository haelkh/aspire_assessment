"""Configuration settings for the ArcVault Triage workflow."""

import os

# === Routing Configuration ===
QUEUE_MAPPING = {
    "Bug Report": "Engineering",
    "Feature Request": "Product",
    "Billing Issue": "Billing",
    "Technical Question": "IT/Security",
    "Incident/Outage": "Engineering"
}

# Destination used when any escalation rule is triggered.
ESCALATION_QUEUE = "Human Review"

# Pipeline version emitted in responses and records.
PIPELINE_VERSION = os.getenv("PIPELINE_VERSION", "1.1.0")

# === Escalation Configuration ===
ESCALATION_CONFIDENCE_THRESHOLD = 0.70
# Escalate billing issues when amount delta exceeds this threshold.
BILLING_ESCALATION_DELTA_THRESHOLD = 500.0
ESCALATION_KEYWORDS = [
    "outage",
    "down for all users",
    "billing error",
    "security breach",
    "data loss",
    "critical issue",
    "critical failure",
    "urgent issue",
    "multiple users affected",
    "system down",
    "service unavailable",
    "all users affected",
    "all users impacted",
    "entire team",
    "platform down",
    "cannot access",
]
BILLING_DISPUTE_KEYWORDS = [
    "overcharge",
    "overcharged",
    "billing error",
    "invoice error",
    "incorrect charge",
    "wrong charge",
    "charge discrepancy",
]

# === Category Definitions ===
CATEGORIES = [
    "Bug Report",
    "Feature Request",
    "Billing Issue",
    "Technical Question",
    "Incident/Outage"
]

PRIORITIES = [
    "Low",
    "Medium",
    "High"
]

# === Available Queues ===
QUEUES = [
    "Engineering",
    "Product",
    "Billing",
    "IT/Security",
    ESCALATION_QUEUE
]

# === Intake Validation Configuration ===
MAX_MESSAGE_LENGTH = 5000
MAX_REQUEST_ID_LENGTH = 128
MAX_CUSTOMER_ID_LENGTH = 128
MAX_EXTERNAL_ID_LENGTH = 128
MAX_CHANNEL_METADATA_KEYS = 25

# === Persistence Configuration ===
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
OUTPUT_JSONL_PATH = os.getenv(
    "OUTPUT_JSONL_PATH",
    os.path.join(OUTPUT_DIR, "processed_records.jsonl"),
)
IDEMPOTENCY_DB_PATH = os.getenv(
    "IDEMPOTENCY_DB_PATH",
    os.path.join(OUTPUT_DIR, "triage_state.db"),
)
