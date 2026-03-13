"""Verification test for enrichment guardrail flags."""
from workflow.nodes import enrich_node

class _FakeClientEnrichmentFailure:
    def generate_json(self, prompt: str) -> dict:
        raise RuntimeError("simulated API failure")

def test_enrich_node_surfaces_guardrail_flags(monkeypatch) -> None:
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

    assert "enrichment_guardrail_flags" in result
    assert any(flag.startswith("enrichment_error:RuntimeError") for flag in result["enrichment_guardrail_flags"])
