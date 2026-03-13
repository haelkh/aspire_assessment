"""
State schema for the ArcVault Triage workflow.

This module defines the TriageState TypedDict that represents the state
passed between nodes in the LangGraph workflow.
"""

from typing import TypedDict, Optional


class TriageState(TypedDict, total=False):
    """
    State schema for the triage workflow.

    This state is passed between nodes and accumulates information
    as the message is processed through the pipeline.
    """

    # === Input Fields ===
    message: str
    """The raw customer message content."""

    source: str
    """Where the message came from: Email, Web Form, or Support Portal."""

    # === Classification Fields ===
    category: str
    """
    The classified category. One of:
    - Bug Report: Technical issues, errors, broken functionality
    - Feature Request: Requests for new features or enhancements
    - Billing Issue: Payment, invoice, subscription problems
    - Technical Question: How-to questions, configuration help
    - Incident/Outage: System down, widespread issues affecting multiple users
    """

    priority: str
    """
    The assigned priority. One of:
    - High: System down, billing errors, security issues, multiple users affected
    - Medium: Feature requests, non-critical bugs, account issues
    - Low: General questions, minor enhancement suggestions
    """

    confidence: float
    """
    Model confidence in the classification.
    Float between 0.0 and 1.0.
    Values below 0.70 trigger human escalation.
    """

    # === Enrichment Fields ===
    core_issue: str
    """One sentence summarizing the main problem or request."""

    identifiers: list[str]
    """List of extracted identifiers (account IDs, invoice numbers, error codes, URLs)."""

    urgency_signal: str
    """Explanation of why this might be urgent, or 'None' if not urgent."""

    human_summary: str
    """
    2-3 sentence summary for the receiving team.
    Should explain the issue in plain language.
    """

    # === Routing Fields ===
    destination_queue: str
    """
    The team/queue this ticket should be routed to.
    Final destination queue.
    If escalated, this is set to Human Review.
    """

    proposed_queue: str
    """
    Queue derived from category mapping before escalation override.
    One of: Engineering, Billing, Product, IT/Security
    """

    escalation_flag: bool
    """Whether this ticket requires human review before routing."""

    escalation_rules_triggered: list[str]
    """Machine-readable list of escalation rules that were matched."""

    escalation_reason: Optional[str]
    """If escalation_flag is True, explains why (low confidence or keyword trigger)."""

    # === Output Fields ===
    timestamp: str
    """ISO format timestamp when the record was processed."""

    record_id: Optional[str]
    """Unique identifier for this processed record."""
