"""Webhook API contract tests."""

from fastapi.testclient import TestClient

import ingestion.webhook_api as webhook_api


def _fake_result(message: str, source: str, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
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
        "ingestion_id": metadata.get("ingestion_id"),
        "request_id": metadata.get("request_id"),
        "customer_id": metadata.get("customer_id"),
        "received_at": metadata.get("received_at"),
        "channel_metadata": metadata.get("channel_metadata"),
    }


def test_health_endpoint() -> None:
    client = TestClient(webhook_api.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_intake_legacy_payload_returns_processed_record(monkeypatch) -> None:
    monkeypatch.delenv("INTAKE_API_KEY", raising=False)
    monkeypatch.setattr(webhook_api, "process_message", _fake_result)

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
    assert body["request_id"] == "REQ-1234"
    assert "ingestion_id" in body


def test_intake_accepts_new_optional_fields(monkeypatch) -> None:
    monkeypatch.delenv("INTAKE_API_KEY", raising=False)
    monkeypatch.setattr(webhook_api, "process_message", _fake_result)

    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={
            "source": "Web Form",
            "message": "Need help with setup.",
            "request_id": "REQ-999",
            "customer_id": "cust-42",
            "received_at": "2026-03-13T11:00:00",
            "channel_metadata": {"ip": "1.2.3.4", "form_id": "contact-us"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "REQ-999"
    assert body["customer_id"] == "cust-42"
    assert body["received_at"] == "2026-03-13T11:00:00"
    assert body["channel_metadata"]["form_id"] == "contact-us"


def test_intake_rejects_missing_api_key_when_enforced(monkeypatch) -> None:
    monkeypatch.setenv("INTAKE_API_KEY", "secret-key")
    monkeypatch.setattr(webhook_api, "process_message", _fake_result)

    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={"source": "Email", "message": "Login fails for users."},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-API-Key header."


def test_intake_rejects_invalid_api_key_when_enforced(monkeypatch) -> None:
    monkeypatch.setenv("INTAKE_API_KEY", "secret-key")
    monkeypatch.setattr(webhook_api, "process_message", _fake_result)

    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={"source": "Email", "message": "Login fails for users."},
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key."


def test_intake_accepts_valid_api_key_when_enforced(monkeypatch) -> None:
    monkeypatch.setenv("INTAKE_API_KEY", "secret-key")
    monkeypatch.setattr(webhook_api, "process_message", _fake_result)

    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={"source": "Email", "message": "Login fails for users."},
        headers={"X-API-Key": "secret-key"},
    )

    assert response.status_code == 200
    assert response.json()["category"] == "Bug Report"
    assert response.json()["confidence_level"] == "High"
    assert response.json()["confidence_source"] == "model"


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


def test_intake_blank_message_returns_validation_error() -> None:
    client = TestClient(webhook_api.app)
    response = client.post(
        "/intake",
        json={
            "source": "Email",
            "message": "   ",
        },
    )

    assert response.status_code == 422
