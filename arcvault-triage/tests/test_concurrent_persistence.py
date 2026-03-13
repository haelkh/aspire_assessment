"""Concurrency tests for persistence safety."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import integrations.sheets_client as sheets_client_module
from storage.idempotency_store import reset_idempotency_store_for_tests
from workflow.nodes import output_node


class _DummySheetsClient:
    def append_record(self, record):  # noqa: ANN001
        return 1


def _build_state(index: int) -> dict:
    return {
        "source": "Email",
        "message": f"Concurrent message {index}",
        "request_id": f"req-{index}",
        "category": "Bug Report",
        "priority": "Medium",
        "confidence": 0.9,
        "classification_guardrail_flags": [],
        "core_issue": "Concurrent test message.",
        "identifiers": [],
        "urgency_signal": "None",
        "proposed_queue": "Engineering",
        "destination_queue": "Engineering",
        "escalation_flag": False,
        "escalation_rules_triggered": [],
        "escalation_rule_evidence": [],
        "escalation_reason": None,
        "human_summary": "Concurrent write validation.",
        "pipeline_version": "1.1.0",
        "ingestion_id": f"ing-{index}",
        "processing_started_at": 0.0,
    }


def test_concurrent_intake_writes_do_not_corrupt_jsonl(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    reset_idempotency_store_for_tests(str(tmp_path / "output" / "triage_state.db"))
    monkeypatch.setattr(
        sheets_client_module,
        "get_sheets_client",
        lambda: _DummySheetsClient(),
    )

    states = [_build_state(index) for index in range(30)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(output_node, states))

    assert all(result["output_saved"] is True for result in results)

    output_path = tmp_path / "output" / "processed_records.jsonl"
    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 30

    parsed = [json.loads(line) for line in lines]
    request_ids = {record["request_id"] for record in parsed}
    assert len(request_ids) == 30
