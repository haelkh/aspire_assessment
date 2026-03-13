"""Routing and low-confidence escalation tests."""

from config.settings import ESCALATION_QUEUE
from workflow.nodes import route_node


def test_low_confidence_routes_to_human_review() -> None:
    state = {
        "category": "Bug Report",
        "confidence": 0.62,
        "message": "Login fails with 403 for one user.",
    }

    result = route_node(state)

    assert result["proposed_queue"] == "Engineering"
    assert result["destination_queue"] == ESCALATION_QUEUE
    assert result["escalation_flag"] is True
    assert "low_confidence" in result["escalation_rules_triggered"]
    assert "Low confidence score" in result["escalation_reason"]


def test_non_escalated_destination_matches_proposed_queue() -> None:
    state = {
        "category": "Feature Request",
        "confidence": 0.95,
        "message": "Please add CSV export for reports.",
    }

    result = route_node(state)

    assert result["escalation_flag"] is False
    assert result["proposed_queue"] == "Product"
    assert result["destination_queue"] == "Product"
