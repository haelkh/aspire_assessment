"""
Google Sheets client for the ArcVault Triage workflow.

This module provides functionality to write processed records
to a Google Sheet for easy visualization and sharing.
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

load_dotenv()


class SheetsClient:
    """
    Client for interacting with Google Sheets.

    This client handles authentication and writing records to
    a configured Google Sheet.
    """

    # Column headers matching the expected sheet structure
    HEADERS = [
        "Record ID",
        "Ingestion ID",
        "Pipeline Version",
        "Processing (ms)",
        "Replay",
        "Request ID",
        "Customer ID",
        "Received At",
        "Timestamp",
        "Source",
        "Message",
        "Category",
        "Priority",
        "Confidence",
        "Confidence Level",
        "Confidence Source",
        "Guardrail Flags",
        "Core Issue",
        "Identifiers",
        "Urgency",
        "Proposed Queue",
        "Final Queue",
        "Escalation",
        "Escalation Rules",
        "Escalation Evidence",
        "Escalation Reason",
        "Summary"
    ]

    def __init__(
        self,
        spreadsheet_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize the Google Sheets client.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID.
                If not provided, reads from GOOGLE_SHEETS_SPREADSHEET_ID env var.
            credentials_path: Path to service account JSON credentials.
                If not provided, reads from GOOGLE_CREDENTIALS_PATH env var.
        """
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        
        env_cred_path = credentials_path or os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            "credentials/service_account.json"
        )
        
        # If relative, resolve it against the project root (parent of integrations/)
        if not os.path.isabs(env_cred_path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.credentials_path = os.path.join(project_root, env_cred_path)
        else:
            self.credentials_path = env_cred_path

        if not self.spreadsheet_id:
            raise ValueError(
                "Spreadsheet ID is required. Set GOOGLE_SHEETS_SPREADSHEET_ID "
                "environment variable or pass spreadsheet_id parameter."
            )

        self._client = None
        self._sheet = None
        self._headers_ready = False
        self._header_column_map: Dict[str, int] = {}

    @staticmethod
    def _column_letter(index: int) -> str:
        """Convert a 1-based column index to A1-style column letters."""
        if index < 1:
            raise ValueError("Column index must be >= 1")

        letters: List[str] = []
        value = index
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            letters.append(chr(65 + remainder))
        return "".join(reversed(letters))

    def _header_range(self) -> str:
        end_col = self._column_letter(len(self.HEADERS))
        return f"A1:{end_col}1"

    def _row_range(self, row_number: int, end_column: int) -> str:
        end_col = self._column_letter(end_column)
        return f"A{row_number}:{end_col}{row_number}"

    def _rows_range(self, start_row: int, end_row: int, end_column: int) -> str:
        end_col = self._column_letter(end_column)
        return f"A{start_row}:{end_col}{end_row}"

    @staticmethod
    def _normalize_header_name(value: str) -> str:
        return " ".join(str(value).strip().lower().split())

    def _trim_or_pad_headers(self, headers: List[str]) -> List[str]:
        expected_len = len(self.HEADERS)
        normalized = [str(value).strip() for value in headers]

        if len(normalized) < expected_len:
            normalized.extend([""] * (expected_len - len(normalized)))

        return normalized[:expected_len]

    def _build_header_column_map(self, headers: List[str]) -> Dict[str, int]:
        """
        Build a map from expected header name to 1-based column index in sheet.

        Raises:
            ValueError: if a required header is missing.
        """
        name_to_indexes: Dict[str, List[int]] = {}
        for index, header in enumerate(headers, start=1):
            normalized = self._normalize_header_name(header)
            if not normalized:
                continue
            name_to_indexes.setdefault(normalized, []).append(index)

        column_map: Dict[str, int] = {}
        missing: List[str] = []
        for expected in self.HEADERS:
            normalized_expected = self._normalize_header_name(expected)
            indexes = name_to_indexes.get(normalized_expected, [])
            if not indexes:
                missing.append(expected)
                continue
            # If a header appears multiple times, use the left-most match.
            column_map[expected] = indexes[0]

        if missing:
            details: List[str] = []
            if missing:
                details.append(
                    "missing: " + ", ".join(f"'{name}'" for name in missing[:5])
                )
            detail_text = "; ".join(details) if details else "invalid headers"
            raise ValueError(
                "Google Sheets headers mismatch in row 1. "
                f"Expected headers could not be resolved ({detail_text})."
            )

        return column_map

    def _serialize_row_by_header_map(self, row_values: List[str]) -> List[str]:
        """
        Serialize a logical row into sheet column order based on header mapping.

        The returned list always starts at column A and extends to the rightmost
        expected header column currently present in row 1.
        """
        if len(row_values) != len(self.HEADERS):
            raise ValueError(
                "Row length mismatch for Google Sheets write. "
                f"Expected {len(self.HEADERS)} columns, got {len(row_values)}."
            )

        if not self._header_column_map:
            raise ValueError("Google Sheets headers are not initialized.")

        rightmost_column = max(self._header_column_map.values())
        serialized = [""] * rightmost_column

        for header_name, value in zip(self.HEADERS, row_values):
            column_index = self._header_column_map[header_name]
            serialized[column_index - 1] = value

        return serialized

    def _ensure_headers(self) -> None:
        """
        Ensure row 1 contains all expected headers and build a column map.

        Behavior:
        - If row 1 is empty in A..AA, write headers automatically.
        - If row 1 has expected headers in any order, writes are mapped by name.
        - If headers are invalid and there is no data, row 1 is rewritten.
        - If headers are invalid and data exists, fail loudly.
        """
        if self._headers_ready:
            return

        expected_headers = [header.strip() for header in self.HEADERS]
        raw_header_row = [str(value).strip() for value in self._sheet.row_values(1)]
        existing_headers = self._trim_or_pad_headers(raw_header_row)

        if all(value == "" for value in existing_headers):
            self._sheet.update(
                range_name=self._header_range(),
                values=[expected_headers],
                value_input_option="RAW",
            )
            self._header_column_map = {
                header: index for index, header in enumerate(self.HEADERS, start=1)
            }
            self._headers_ready = True
            return

        try:
            self._header_column_map = self._build_header_column_map(raw_header_row)
            self._headers_ready = True
            return
        except ValueError as original_error:
            # Auto-repair when sheet has no data rows yet.
            if len(self._sheet.get_all_values()) <= 1:
                self._sheet.update(
                    range_name=self._header_range(),
                    values=[expected_headers],
                    value_input_option="RAW",
                )
                self._header_column_map = {
                    header: index for index, header in enumerate(self.HEADERS, start=1)
                }
                self._headers_ready = True
                return
            raise original_error

        self._headers_ready = True

    def _next_row_number(self) -> int:
        """Return the next writable row index after existing data."""
        all_values = self._sheet.get_all_values()
        if not all_values:
            return 2
        return len(all_values) + 1

    def _connect(self):
        """Establish connection to Google Sheets."""
        if self._sheet is not None:
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            # Load credentials
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found: {self.credentials_path}\n"
                    "Please download your service account JSON from Google Cloud Console."
                )

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes
            )

            self._client = gspread.authorize(credentials)
            self._sheet = self._client.open_by_key(self.spreadsheet_id).sheet1
            self._headers_ready = False
            self._header_column_map = {}

        except ImportError:
            raise ImportError(
                "gspread and google-auth packages are required. "
                "Install with: pip install gspread google-auth"
            )

    def append_record(self, record: Dict[str, Any]) -> int:
        """
        Append a record to the Google Sheet.

        Args:
            record: Dictionary containing the record data.

        Returns:
            The row number where the record was appended.

        Raises:
            ValueError: If required fields are missing.
        """
        self._connect()
        self._ensure_headers()

        # Format the record as a row
        row = self._serialize_row_by_header_map(self._format_row(record))

        # Write to an explicit range to prevent table-detection column drift.
        row_number = self._next_row_number()
        end_column = max(self._header_column_map.values())
        self._sheet.update(
            range_name=self._row_range(row_number, end_column),
            values=[row],
            value_input_option="RAW",
        )
        return row_number

    def append_records(self, records: List[Dict[str, Any]]) -> int:
        """
        Append multiple records to the Google Sheet.

        Args:
            records: List of record dictionaries.

        Returns:
            The number of records appended.
        """
        self._connect()
        self._ensure_headers()

        rows = [self._serialize_row_by_header_map(self._format_row(record)) for record in records]
        if not rows:
            return 0

        start_row = self._next_row_number()
        end_row = start_row + len(rows) - 1
        end_column = max(self._header_column_map.values())
        self._sheet.update(
            range_name=self._rows_range(start_row, end_row, end_column),
            values=rows,
            value_input_option="RAW",
        )
        return len(records)

    def _format_row(self, record: Dict[str, Any]) -> List[str]:
        """
        Format a record dictionary as a row for the sheet.

        Args:
            record: Dictionary containing the record data.

        Returns:
            List of string values for each column.
        """
        # Truncate message for readability
        message = record.get("message", "")
        if len(message) > 200:
            message = message[:197] + "..."

        # Format identifiers as comma-separated string
        identifiers = record.get("identifiers", [])
        if isinstance(identifiers, list):
            identifiers = ", ".join(str(i) for i in identifiers)
        else:
            identifiers = str(identifiers)

        return [
            record.get("record_id", ""),
            record.get("ingestion_id", ""),
            record.get("pipeline_version", ""),
            f"{record.get('processing_ms', 0.0):.2f}",
            "YES" if record.get("idempotent_replay", False) else "NO",
            record.get("request_id", ""),
            record.get("customer_id", ""),
            record.get("received_at", ""),
            record.get("timestamp", datetime.now().isoformat()),
            record.get("source", ""),
            message,
            record.get("category", ""),
            record.get("priority", ""),
            f"{record.get('confidence', 0):.2f}",
            record.get("confidence_level", ""),
            record.get("confidence_source", ""),
            ", ".join(record.get("classification_guardrail_flags", [])),
            record.get("core_issue", ""),
            identifiers,
            record.get("urgency_signal", ""),
            record.get("proposed_queue", record.get("destination_queue", "")),
            record.get("destination_queue", ""),
            "YES" if record.get("escalation_flag", False) else "NO",
            ", ".join(record.get("escalation_rules_triggered", [])),
            " | ".join(record.get("escalation_rule_evidence", [])),
            record.get("escalation_reason", ""),
            record.get("human_summary", "")
        ]

    def get_all_records(self) -> List[Dict[str, Any]]:
        """
        Get all records from the sheet.

        Returns:
            List of record dictionaries.
        """
        self._connect()
        return self._sheet.get_all_records()

    def clear_records(self):
        """Clear all records from the sheet (except headers)."""
        self._connect()
        records = self._sheet.get_all_records()
        if records:
            self._sheet.delete_rows(2, len(records) + 1)


# Global client instance (initialized lazily)
_client: Optional[SheetsClient] = None


def get_sheets_client() -> SheetsClient:
    """
    Get or create the global Sheets client instance.

    Returns:
        SheetsClient instance.
    """
    global _client
    if _client is None:
        _client = SheetsClient()
    return _client


def write_record(record: Dict[str, Any]) -> int:
    """
    Convenience function to write a record to Google Sheets.

    Args:
        record: Dictionary containing the record data.

    Returns:
        The row number where the record was appended.
    """
    client = get_sheets_client()
    return client.append_record(record)
