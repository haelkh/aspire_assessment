"""Keyword-based escalation tests."""

from config.settings import ESCALATION_QUEUE
from workflow.nodes import route_node


def test_keyword_match_routes_to_human_review() -> None:
    state = {
        "category": "Incident/Outage",
        "confidence": 0.96,
        "message": "Dashboard is down for all users and this looks like an outage.",
    }

    result = route_node(state)

    assert result["escalation_flag"] is True
    assert result["destination_queue"] == ESCALATION_QUEUE
    assert any(rule.startswith("keyword:") for rule in result["escalation_rules_triggered"])
    assert "Escalation keywords detected" in result["escalation_reason"]
