"""Output schema and persistence tests."""

import json
from pathlib import Path

import integrations.sheets_client as sheets_client_module
from workflow.nodes import output_node, _processed_hashes


class _DummySheetsClient:
    def append_record(self, record):  # noqa: ANN001
        return 1


def _make_state(**overrides):
    """Build a valid state dict for output_node with sensible defaults."""
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
    state.update(overrides)
    return state


def test_output_record_contains_required_fields(tmp_path: Path, monkeypatch) -> None:
    _processed_hashes.clear()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    state = _make_state()
    result = output_node(state)

    assert result["output_saved"] is True
    assert "timestamp" in result

    output_path = tmp_path / "output" / "processed_records.json"
    assert output_path.exists()

    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(records) == 1
    record = records[0]

    required_fields = [
        "record_id",
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


def test_record_id_present_in_output(tmp_path: Path, monkeypatch) -> None:
    """Output records must include a deterministic record_id."""
    _processed_hashes.clear()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    result = output_node(_make_state())
    assert "record_id" in result
    assert isinstance(result["record_id"], str)
    assert len(result["record_id"]) == 16


def test_deduplication_prevents_duplicate_records(tmp_path: Path, monkeypatch) -> None:
    """Processing the same message twice should only write one record."""
    _processed_hashes.clear()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    state = _make_state()

    # First call should succeed
    result1 = output_node(state)
    assert result1["output_saved"] is True

    # Second call with the same message should be marked as duplicate
    result2 = output_node(state)
    assert result2.get("duplicate") is True
    assert result2["output_saved"] is False

    # Only one record should be persisted
    output_path = tmp_path / "output" / "processed_records.json"
    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(records) == 1
