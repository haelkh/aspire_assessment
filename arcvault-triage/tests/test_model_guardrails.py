"""LLM output validation and strict guardrail tests."""

import pytest

from workflow.nodes import classify_node, enrich_node


class _FakeClientInvalidClassification:
    def generate_json(self, prompt: str) -> dict:  # noqa: ARG002
        return {
            "category": "Unknown Category",
            "priority": "Urgent",
            "confidence": "not-a-number",
        }


class _FakeClientEnrichmentFailure:
    def generate_json(self, prompt: str) -> dict:  # noqa: ARG002
        raise RuntimeError("simulated API failure")


class _FakeClientValidClassification:
    def generate_json(self, prompt: str) -> dict:  # noqa: ARG002
        return {
            "category": "Bug Report",
            "priority": "High",
            "confidence": 0.91,
        }


class _FakeClientRuntimeFailure:
    def generate_json(self, prompt: str) -> dict:  # noqa: ARG002
        raise RuntimeError("simulated quota error")


def test_classify_node_rejects_invalid_model_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "workflow.nodes.get_gemini_client",
        lambda: _FakeClientInvalidClassification(),
    )

    with pytest.raises(RuntimeError, match="Classification failed guardrails"):
        classify_node({"message": "Test message", "source": "Email"})


def test_classify_node_returns_confidence_metadata_on_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "workflow.nodes.get_gemini_client",
        lambda: _FakeClientValidClassification(),
    )

    result = classify_node({"message": "Test message", "source": "Email"})

    assert result["category"] == "Bug Report"
    assert result["priority"] == "High"
    assert result["confidence"] == 0.91
    assert result["confidence_level"] == "High"
    assert result["confidence_source"] == "model"
    assert result["classification_guardrail_flags"] == []


def test_classify_node_raises_on_runtime_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "workflow.nodes.get_gemini_client",
        lambda: _FakeClientRuntimeFailure(),
    )

    with pytest.raises(RuntimeError) as exc_info:
        classify_node({"message": "Test message", "source": "Email"})

    message = str(exc_info.value)
    assert "classification_error:RuntimeError" in message
    assert "invalid_category" not in message
    assert "invalid_priority" not in message
    assert "invalid_confidence" not in message


def test_enrich_node_returns_safe_fallback_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "workflow.nodes.get_gemini_client",
        lambda: _FakeClientEnrichmentFailure(),
    )

    state = {
        "message": "Need help with SSO setup.",
        "category": "Technical Question",
        "priority": "Medium",
    }
    result = enrich_node(state)

    assert isinstance(result["core_issue"], str) and result["core_issue"]
    assert isinstance(result["identifiers"], list)
    assert isinstance(result["human_summary"], str) and result["human_summary"]
