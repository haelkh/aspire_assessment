"""
Configuration settings for the ArcVault Triage workflow.
"""

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
