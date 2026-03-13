"""SQLite-backed idempotency store for processed requests."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from config.settings import IDEMPOTENCY_DB_PATH


class IdempotencyStore:
    """Persist deduplication keys so replay detection survives restarts."""

    def __init__(self, db_path: str = IDEMPOTENCY_DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_requests (
                    dedup_key TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    source TEXT,
                    request_id TEXT,
                    first_seen_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def register_or_replay(
        self,
        dedup_key: str,
        record_id: str,
        source: str,
        request_id: Optional[str] = None,
    ) -> bool:
        """
        Register a dedup key.

        Returns:
            True when key already exists (replay), False on first-seen insert.
        """
        with self._lock:
            with self._connect() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO processed_requests
                            (dedup_key, record_id, source, request_id, first_seen_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            dedup_key,
                            record_id,
                            source,
                            request_id,
                            datetime.utcnow().isoformat(),
                        ),
                    )
                    conn.commit()
                    return False
                except sqlite3.IntegrityError:
                    return True

    def clear(self) -> None:
        """Delete all idempotency entries (used by tests)."""
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM processed_requests")
                conn.commit()


_store: Optional[IdempotencyStore] = None
_store_lock = threading.Lock()


def get_idempotency_store() -> IdempotencyStore:
    """Get or create the process-global idempotency store."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = IdempotencyStore()
    return _store


def reset_idempotency_store_for_tests(db_path: str) -> None:
    """Reset global store to a specific path for deterministic test isolation."""
    global _store
    with _store_lock:
        _store = IdempotencyStore(db_path=db_path)
