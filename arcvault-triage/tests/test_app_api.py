"""Web UI API contract tests."""

from fastapi.testclient import TestClient

import app as app_module


def _fake_success(message: str, source: str, metadata: dict | None = None) -> dict:  # noqa: ARG001
    return {
        "source": source,
        "message": message,
        "category": "Bug Report",
        "priority": "High",
        "confidence": 0.91,
        "confidence_level": "High",
        "confidence_source": "model",
        "classification_guardrail_flags": [],
        "proposed_queue": "Engineering",
        "destination_queue": "Engineering",
        "escalation_flag": False,
        "escalation_rules_triggered": [],
        "escalation_rule_evidence": [],
        "escalation_reason": None,
        "core_issue": "Login failure",
        "identifiers": ["403"],
        "urgency_signal": "Production issue",
        "human_summary": "Users are blocked from logging in.",
        "timestamp": "2026-03-12T00:00:00",
        "record_id": "abc123def4567890",
        "pipeline_version": "1.1.0",
        "processing_ms": 12.0,
        "idempotent_replay": False,
        "ingestion_id": metadata.get("ingestion_id") if metadata else "ing-1",
    }


def _fake_failure(message: str, source: str, metadata: dict | None = None) -> dict:  # noqa: ARG001
    raise RuntimeError("Classification failed guardrails: classification_error:RuntimeError")


def test_triage_returns_confidence_metadata(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "process_message", _fake_success)

    client = TestClient(app_module.app)
    response = client.post(
        "/api/triage",
        json={"source": "Email", "message": "Login fails for users."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confidence"] == 0.91
    assert body["confidence_level"] == "High"
    assert body["confidence_source"] == "model"


def test_triage_surfaces_classification_errors(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "process_message", _fake_failure)

    client = TestClient(app_module.app)
    response = client.post(
        "/api/triage",
        json={"source": "Email", "message": "Login fails for users."},
    )

    assert response.status_code == 502
    assert "Classification failed guardrails" in response.json()["detail"]


def test_batch_includes_confidence_metadata(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "process_message", _fake_success)
    monkeypatch.setattr(
        app_module,
        "SAMPLES",
        [{"id": 1, "source": "Email", "message": "Login fails for users."}],
    )

    client = TestClient(app_module.app)
    response = client.post("/api/batch")

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["confidence"] == 0.91
    assert record["confidence_level"] == "High"
    assert record["confidence_source"] == "model"
