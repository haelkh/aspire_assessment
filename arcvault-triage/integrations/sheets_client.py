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
        "Timestamp",
        "Source",
        "Message",
        "Category",
        "Priority",
        "Confidence",
        "Core Issue",
        "Identifiers",
        "Urgency",
        "Proposed Queue",
        "Final Queue",
        "Escalation",
        "Escalation Rules",
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
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            "credentials/service_account.json"
        )

        if not self.spreadsheet_id:
            raise ValueError(
                "Spreadsheet ID is required. Set GOOGLE_SHEETS_SPREADSHEET_ID "
                "environment variable or pass spreadsheet_id parameter."
            )

        self._client = None
        self._sheet = None

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

        # Format the record as a row
        row = self._format_row(record)

        # Append to sheet
        self._sheet.append_row(row)
        return len(self._sheet.get_all_records()) + 1

    def append_records(self, records: List[Dict[str, Any]]) -> int:
        """
        Append multiple records to the Google Sheet.

        Args:
            records: List of record dictionaries.

        Returns:
            The number of records appended.
        """
        self._connect()

        rows = [self._format_row(record) for record in records]
        self._sheet.append_rows(rows)
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
            record.get("timestamp", datetime.now().isoformat()),
            record.get("source", ""),
            message,
            record.get("category", ""),
            record.get("priority", ""),
            f"{record.get('confidence', 0):.2f}",
            record.get("core_issue", ""),
            identifiers,
            record.get("urgency_signal", ""),
            record.get("proposed_queue", record.get("destination_queue", "")),
            record.get("destination_queue", ""),
            "YES" if record.get("escalation_flag", False) else "NO",
            ", ".join(record.get("escalation_rules_triggered", [])),
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
