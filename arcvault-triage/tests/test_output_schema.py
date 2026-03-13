"""Output schema and persistence tests."""

import json
from pathlib import Path

import integrations.sheets_client as sheets_client_module
from storage.idempotency_store import reset_idempotency_store_for_tests
from workflow.nodes import output_node


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
        "classification_guardrail_flags": [],
        "core_issue": "Users cannot log in after deployment.",
        "identifiers": ["403"],
        "urgency_signal": "Production login failure.",
        "proposed_queue": "Engineering",
        "destination_queue": "Human Review",
        "escalation_flag": True,
        "escalation_rules_triggered": ["keyword:outage"],
        "escalation_rule_evidence": ["matched_keyword='outage'"],
        "escalation_reason": "Escalation keywords detected: outage",
        "human_summary": "Multiple users are blocked from login and require urgent triage.",
        "ingestion_id": "ing-123",
        "pipeline_version": "1.1.0",
        "processing_started_at": 0.0,
    }
    state.update(overrides)
    return state


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_output_record_contains_required_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reset_idempotency_store_for_tests(str(tmp_path / "output" / "triage_state.db"))
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    state = _make_state()
    result = output_node(state)

    assert result["output_saved"] is True
    assert "timestamp" in result

    output_path = tmp_path / "output" / "processed_records.jsonl"
    assert output_path.exists()

    records = _read_jsonl(output_path)
    assert len(records) == 1
    record = records[0]

    required_fields = [
        "record_id",
        "timestamp",
        "pipeline_version",
        "ingestion_id",
        "processing_ms",
        "idempotent_replay",
        "source",
        "message",
        "category",
        "priority",
        "confidence",
        "classification_guardrail_flags",
        "core_issue",
        "identifiers",
        "urgency_signal",
        "proposed_queue",
        "destination_queue",
        "escalation_flag",
        "escalation_rules_triggered",
        "escalation_rule_evidence",
        "escalation_reason",
        "human_summary",
    ]
    for field in required_fields:
        assert field in record


def test_record_id_present_in_output(tmp_path: Path, monkeypatch) -> None:
    """Output records must include a deterministic record_id."""
    monkeypatch.chdir(tmp_path)
    reset_idempotency_store_for_tests(str(tmp_path / "output" / "triage_state.db"))
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
    monkeypatch.chdir(tmp_path)
    reset_idempotency_store_for_tests(str(tmp_path / "output" / "triage_state.db"))
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    state = _make_state()

    # First call should succeed.
    result1 = output_node(state)
    assert result1["output_saved"] is True
    assert result1["idempotent_replay"] is False

    # Second call with the same content should be marked as replay.
    result2 = output_node(state)
    assert result2.get("duplicate") is True
    assert result2["output_saved"] is False
    assert result2["idempotent_replay"] is True

    # Only one record should be persisted.
    output_path = tmp_path / "output" / "processed_records.jsonl"
    records = _read_jsonl(output_path)
    assert len(records) == 1
