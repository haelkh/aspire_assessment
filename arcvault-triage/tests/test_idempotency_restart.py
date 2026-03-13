"""Idempotency replay behavior across store reinitialization."""

from pathlib import Path

import integrations.sheets_client as sheets_client_module
from storage.idempotency_store import reset_idempotency_store_for_tests
from workflow.nodes import output_node


class _DummySheetsClient:
    def append_record(self, record):  # noqa: ANN001
        return 1


def _state() -> dict:
    return {
        "source": "Support Portal",
        "message": "Invoice charge mismatch detected.",
        "request_id": "req-restart-1",
        "category": "Billing Issue",
        "priority": "High",
        "confidence": 0.95,
        "classification_guardrail_flags": [],
        "core_issue": "Billing mismatch requires review.",
        "identifiers": ["INV-1001"],
        "urgency_signal": "Financial impact",
        "proposed_queue": "Billing",
        "destination_queue": "Billing",
        "escalation_flag": False,
        "escalation_rules_triggered": [],
        "escalation_rule_evidence": [],
        "escalation_reason": None,
        "human_summary": "Invoice mismatch from customer.",
        "pipeline_version": "1.1.0",
        "ingestion_id": "ing-restart",
        "processing_started_at": 0.0,
    }


def test_duplicate_request_replay_survives_store_reinit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "output" / "triage_state.db"
    reset_idempotency_store_for_tests(str(db_path))
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    first = output_node(_state())
    assert first["output_saved"] is True
    assert first["idempotent_replay"] is False

    # Simulate process restart by reinitializing singleton from existing DB.
    reset_idempotency_store_for_tests(str(db_path))
    second = output_node(_state())
    assert second["output_saved"] is False
    assert second["idempotent_replay"] is True
