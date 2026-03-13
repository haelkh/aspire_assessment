"""Webhook API contract tests."""

from fastapi.testclient import TestClient

import ingestion.webhook_api as webhook_api


def test_health_endpoint() -> None:
    client = TestClient(webhook_api.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_intake_valid_payload_returns_processed_record(monkeypatch) -> None:
    def _fake_process_message(message: str, source: str) -> dict:
        return {
            "source": source,
            "message": message,
            "category": "Bug Report",
            "priority": "High",
            "confidence": 0.91,
            "proposed_queue": "Engineering",
            "destination_queue": "Engineering",
            "escalation_flag": False,
            "escalation_rules_triggered": [],
            "escalation_reason": None,
            "core_issue": "Login failure",
            "identifiers": ["403"],
            "urgency_signal": "Production issue",
            "human_summary": "Users are blocked from logging in.",
            "timestamp": "2026-03-12T00:00:00",
        }

    monkeypatch.setattr(webhook_api, "process_message", _fake_process_message)

    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={
            "source": "Email",
            "message": "Login fails for users.",
            "external_id": "REQ-1234",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "Email"
    assert body["category"] == "Bug Report"
    assert body["external_id"] == "REQ-1234"


def test_intake_invalid_source_returns_validation_error() -> None:
    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={
            "source": "SMS",
            "message": "This should fail validation.",
        },
    )

    assert response.status_code == 422
