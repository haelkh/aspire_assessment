"""Submission artifact generation tests."""

import json
from pathlib import Path

import scripts.generate_submission_artifacts as submission_script


class _DummyStore:
    def clear(self) -> None:
        return None


def _fake_process_message(message: str, source: str) -> dict:  # noqa: ARG001
    return {
        "record_id": "abc123def4567890",
        "ingestion_id": "ing-1",
        "pipeline_version": "1.1.0",
        "processing_ms": 10.0,
        "idempotent_replay": False,
        "request_id": None,
        "customer_id": None,
        "received_at": None,
        "category": "Technical Question",
        "priority": "Medium",
        "confidence": 0.88,
        "classification_guardrail_flags": [],
        "core_issue": "Question about product behavior.",
        "identifiers": [],
        "urgency_signal": "None",
        "proposed_queue": "IT/Security",
        "destination_queue": "IT/Security",
        "escalation_flag": False,
        "escalation_rules_triggered": [],
        "escalation_rule_evidence": [],
        "escalation_reason": None,
        "human_summary": "Customer asked a technical question.",
        "timestamp": "2026-03-13T00:00:00",
    }


def test_submission_artifacts_generate_five_sorted_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "output"
    submission_json = output_dir / "submission_records.json"
    submission_summary = output_dir / "submission_summary.md"

    monkeypatch.setattr(submission_script, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(submission_script, "SUBMISSION_JSON", submission_json)
    monkeypatch.setattr(submission_script, "SUBMISSION_SUMMARY", submission_summary)
    monkeypatch.setattr(submission_script, "process_message", _fake_process_message)
    monkeypatch.setattr(submission_script, "get_idempotency_store", lambda: _DummyStore())

    paths = submission_script.generate_submission_artifacts()
    assert paths["json_path"] == str(submission_json)
    assert paths["summary_path"] == str(submission_summary)

    records = json.loads(submission_json.read_text(encoding="utf-8"))
    assert len(records) == 5
    assert [record["sample_id"] for record in records] == [1, 2, 3, 4, 5]
