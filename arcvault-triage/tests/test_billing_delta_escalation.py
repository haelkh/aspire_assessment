"""Billing delta escalation tests."""

from config.settings import ESCALATION_QUEUE
from workflow.nodes import route_node


def test_billing_amount_delta_above_threshold_escalates() -> None:
    state = {
        "category": "Billing Issue",
        "confidence": 0.98,
        "message": (
            "Invoice #1002 charged us $1,900 but our contract is $1,200. "
            "Please fix this billing error."
        ),
    }

    result = route_node(state)

    assert result["escalation_flag"] is True
    assert result["destination_queue"] == ESCALATION_QUEUE
    assert any(
        rule.startswith("billing_delta_exceeds_threshold:")
        for rule in result["escalation_rules_triggered"]
    )
    assert "Billing amount delta exceeds threshold" in result["escalation_reason"]


def test_billing_single_amount_with_dispute_language_escalates() -> None:
    state = {
        "category": "Billing Issue",
        "confidence": 0.98,
        "message": "Invoice #1002 shows $1,900 and appears to be an overcharge.",
    }

    result = route_node(state)

    assert result["escalation_flag"] is True
    assert result["destination_queue"] == ESCALATION_QUEUE
    assert any(
        rule.startswith("billing_single_amount_dispute:")
        for rule in result["escalation_rules_triggered"]
    )
    assert "Billing dispute language detected with one amount" in result["escalation_reason"]
