"""
Workflow nodes for the ArcVault Triage system — test helpers.

Expose internal deduplication state for test resets.
"""

from workflow.nodes import _processed_hashes


def reset_dedup_cache() -> None:
    """Clear the in-memory deduplication cache for test isolation."""
    _processed_hashes.clear()
