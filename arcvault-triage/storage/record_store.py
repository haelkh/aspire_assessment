"""Append-safe record writer utilities."""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict

from config.settings import OUTPUT_JSONL_PATH

_write_lock = threading.Lock()


def append_record_jsonl(
    record: Dict[str, Any],
    output_path: str = OUTPUT_JSONL_PATH,
) -> None:
    """Append a single record as one JSON line with a process-local write lock."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    payload = json.dumps(record, ensure_ascii=False)
    with _write_lock:
        with open(output_path, "a", encoding="utf-8") as file_handle:
            file_handle.write(payload + "\n")
