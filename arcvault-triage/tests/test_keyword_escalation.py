"""Keyword escalation tests."""

from config.settings import ESCALATION_QUEUE
from workflow.nodes import route_node


def test_keyword_match_triggers_escalation() -> None:
    state = {
        "category": "Incident/Outage",
        "confidence": 0.95,
        "message": "Dashboard outage — down for all users since 3pm.",
    }

    result = route_node(state)

    assert result["escalation_flag"] is True
    assert result["destination_queue"] == ESCALATION_QUEUE
    assert any(
        rule.startswith("keyword:") for rule in result["escalation_rules_triggered"]
    )
    assert "Escalation keywords detected" in result["escalation_reason"]


def test_keyword_word_boundary_prevents_false_positive() -> None:
    """Substring 'down' should not match when it's part of another word or casual phrase."""
    state = {
        "category": "Feature Request",
        "confidence": 0.95,
        "message": "I'm down for a meeting to discuss the new download feature.",
    }

    result = route_node(state)

    assert result["escalation_flag"] is False
    assert result["destination_queue"] == "Product"
    assert len(result["escalation_rules_triggered"]) == 0
