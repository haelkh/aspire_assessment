"""Test fixtures for workflow state isolation."""

from pathlib import Path

import pytest

from storage.idempotency_store import reset_idempotency_store_for_tests


@pytest.fixture(autouse=True)
def reset_idempotency_store(tmp_path: Path) -> None:
    """Ensure each test uses an isolated SQLite idempotency database."""
    db_path = tmp_path / "output" / "triage_state.db"
    reset_idempotency_store_for_tests(str(db_path))
