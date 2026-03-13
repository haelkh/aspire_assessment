"""LLM output validation and fallback guardrail tests."""

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


def test_classify_node_sanitizes_invalid_model_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "workflow.nodes.get_gemini_client",
        lambda: _FakeClientInvalidClassification(),
    )

    result = classify_node({"message": "Test message", "source": "Email"})

    assert result["category"] == "Technical Question"
    assert result["priority"] == "Medium"
    assert result["confidence"] == 0.0


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
