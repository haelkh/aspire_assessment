"""Output schema and persistence tests."""

import json
from pathlib import Path

import integrations.sheets_client as sheets_client_module
from workflow.nodes import output_node


class _DummySheetsClient:
    def append_record(self, record):  # noqa: ANN001
        return 1


def test_output_record_contains_required_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    state = {
        "source": "Email",
        "message": "Users cannot log in after deployment.",
        "category": "Bug Report",
        "priority": "High",
        "confidence": 0.92,
        "core_issue": "Users cannot log in after deployment.",
        "identifiers": ["403"],
        "urgency_signal": "Production login failure.",
        "proposed_queue": "Engineering",
        "destination_queue": "Human Review",
        "escalation_flag": True,
        "escalation_rules_triggered": ["keyword:outage"],
        "escalation_reason": "Escalation keywords detected: outage",
        "human_summary": "Multiple users are blocked from login and require urgent triage.",
    }

    result = output_node(state)

    assert result["output_saved"] is True
    assert "timestamp" in result

    output_path = tmp_path / "output" / "processed_records.json"
    assert output_path.exists()

    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(records) == 1
    record = records[0]

    required_fields = [
        "timestamp",
        "source",
        "message",
        "category",
        "priority",
        "confidence",
        "core_issue",
        "identifiers",
        "urgency_signal",
        "proposed_queue",
        "destination_queue",
        "escalation_flag",
        "escalation_rules_triggered",
        "escalation_reason",
        "human_summary",
    ]
    for field in required_fields:
        assert field in record
