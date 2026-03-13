"""Google Sheets header validation and write-range tests."""

from __future__ import annotations

import re
from typing import Any, Dict, List

import pytest

from integrations.sheets_client import SheetsClient


class _FakeSheet:
    """Minimal worksheet fake that supports the APIs used by SheetsClient."""

    def __init__(self, rows: List[List[str]] | None = None) -> None:
        self.rows: List[List[str]] = [list(row) for row in rows] if rows else []
        self.update_calls: List[Dict[str, Any]] = []

    def row_values(self, row_index: int) -> List[str]:
        if row_index <= 0 or row_index > len(self.rows):
            return []
        return list(self.rows[row_index - 1])

    def get_all_values(self) -> List[List[str]]:
        return [list(row) for row in self.rows]

    def update(
        self,
        range_name: str | None = None,
        values: List[List[str]] | None = None,
        value_input_option: str | None = None,
    ) -> None:
        if range_name is None or values is None:
            raise AssertionError("range_name and values are required")

        self.update_calls.append(
            {
                "range_name": range_name,
                "values": [list(row) for row in values],
                "value_input_option": value_input_option,
            }
        )

        match = re.match(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$", range_name)
        if not match:
            raise AssertionError(f"Unsupported range format: {range_name}")

        start_col, start_row, _end_col, end_row = match.groups()
        if start_col != "A":
            raise AssertionError("Fake sheet supports only ranges that start at column A")

        start_row_index = int(start_row)
        end_row_index = int(end_row)
        if end_row_index - start_row_index + 1 != len(values):
            raise AssertionError("Range row count does not match values row count")

        for offset, row in enumerate(values):
            target_row = start_row_index + offset
            while len(self.rows) < target_row:
                self.rows.append([])
            self.rows[target_row - 1] = list(row)


def _make_client(sheet: _FakeSheet) -> SheetsClient:
    client = SheetsClient(spreadsheet_id="sheet-id", credentials_path="creds.json")
    client._sheet = sheet  # noqa: SLF001 - test-only dependency injection.
    client._headers_ready = False  # noqa: SLF001 - reset cache for deterministic checks.
    return client


def _sample_record(record_id: str = "rec-1") -> Dict[str, Any]:
    return {
        "record_id": record_id,
        "ingestion_id": "ing-1",
        "pipeline_version": "1.1.0",
        "processing_ms": 12.5,
        "idempotent_replay": False,
        "request_id": "REQ-1",
        "customer_id": "cust-1",
        "received_at": "2026-03-13T10:00:00",
        "timestamp": "2026-03-13T10:00:00",
        "source": "Email",
        "message": "Cannot log in",
        "category": "Bug Report",
        "priority": "High",
        "confidence": 0.92,
        "confidence_level": "High",
        "confidence_source": "model",
        "classification_guardrail_flags": [],
        "core_issue": "Login failure",
        "identifiers": ["403"],
        "urgency_signal": "Production impact",
        "proposed_queue": "Engineering",
        "destination_queue": "Engineering",
        "escalation_flag": False,
        "escalation_rules_triggered": [],
        "escalation_rule_evidence": [],
        "escalation_reason": "",
        "human_summary": "Users cannot log in.",
    }


def test_append_record_initializes_headers_and_writes_explicit_range() -> None:
    sheet = _FakeSheet(rows=[])
    client = _make_client(sheet)

    row_number = client.append_record(_sample_record())

    assert row_number == 2
    assert len(sheet.update_calls) == 2
    assert sheet.update_calls[0]["range_name"] == "A1:AA1"
    assert sheet.update_calls[0]["values"] == [SheetsClient.HEADERS]
    assert sheet.update_calls[1]["range_name"] == "A2:AA2"
    assert len(sheet.update_calls[1]["values"][0]) == len(SheetsClient.HEADERS)


def test_append_record_repairs_headers_when_no_data_rows_exist() -> None:
    bad_headers = list(SheetsClient.HEADERS)
    bad_headers[3] = "Processing Time"
    sheet = _FakeSheet(rows=[bad_headers])
    client = _make_client(sheet)

    row_number = client.append_record(_sample_record())

    assert row_number == 2
    assert len(sheet.update_calls) == 2
    assert sheet.update_calls[0]["range_name"] == "A1:AA1"
    assert sheet.update_calls[0]["values"] == [SheetsClient.HEADERS]
    assert sheet.update_calls[1]["range_name"] == "A2:AA2"


def test_append_record_raises_when_invalid_headers_and_data_exist() -> None:
    bad_headers = list(SheetsClient.HEADERS)
    bad_headers[3] = "Processing Time"
    existing_row = ["existing"] + [""] * (len(SheetsClient.HEADERS) - 1)
    sheet = _FakeSheet(rows=[bad_headers, existing_row])
    client = _make_client(sheet)

    with pytest.raises(ValueError, match="headers mismatch"):
        client.append_record(_sample_record())


def test_append_record_uses_next_row_based_on_existing_values() -> None:
    existing_row = ["existing"] + [""] * (len(SheetsClient.HEADERS) - 1)
    sheet = _FakeSheet(rows=[list(SheetsClient.HEADERS), existing_row])
    client = _make_client(sheet)

    row_number = client.append_record(_sample_record(record_id="rec-2"))

    assert row_number == 3
    assert len(sheet.update_calls) == 1
    assert sheet.update_calls[0]["range_name"] == "A3:AA3"


def test_append_records_writes_single_contiguous_range() -> None:
    sheet = _FakeSheet(rows=[list(SheetsClient.HEADERS)])
    client = _make_client(sheet)

    inserted = client.append_records([_sample_record("rec-10"), _sample_record("rec-11")])

    assert inserted == 2
    assert len(sheet.update_calls) == 1
    assert sheet.update_calls[0]["range_name"] == "A2:AA3"
    assert len(sheet.update_calls[0]["values"]) == 2


def test_append_record_maps_values_by_header_name_when_order_is_rearranged() -> None:
    rearranged_headers = list(SheetsClient.HEADERS)
    message_col = rearranged_headers.pop(10)
    rearranged_headers.insert(2, message_col)

    sheet = _FakeSheet(rows=[rearranged_headers])
    client = _make_client(sheet)

    row_number = client.append_record(_sample_record("rec-map"))

    assert row_number == 2
    assert len(sheet.update_calls) == 1
    update_row = sheet.update_calls[0]["values"][0]

    message_index = rearranged_headers.index("Message")
    pipeline_index = rearranged_headers.index("Pipeline Version")
    assert update_row[message_index] == "Cannot log in"
    assert update_row[pipeline_index] == "1.1.0"
