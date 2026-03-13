"""
Generate deterministic submission artifacts for the ArcVault assessment.

Outputs:
- output/submission_records.json
- output/submission_summary.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from storage.idempotency_store import get_idempotency_store
from workflow.graph import process_message


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLES_PATH = ROOT_DIR / "config" / "sample_inputs.json"
OUTPUT_DIR = ROOT_DIR / "output"
SUBMISSION_JSON = OUTPUT_DIR / "submission_records.json"
SUBMISSION_SUMMARY = OUTPUT_DIR / "submission_summary.md"


def load_samples() -> List[Dict[str, Any]]:
    """Load the five synthetic assessment samples."""
    with open(SAMPLES_PATH, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def build_submission_record(sample: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a deterministic record structure for assessment submission."""
    return {
        "sample_id": sample["id"],
        "record_id": result.get("record_id"),
        "ingestion_id": result.get("ingestion_id"),
        "pipeline_version": result.get("pipeline_version"),
        "processing_ms": result.get("processing_ms"),
        "idempotent_replay": result.get("idempotent_replay"),
        "source": sample["source"],
        "message": sample["message"],
        "request_id": result.get("request_id"),
        "customer_id": result.get("customer_id"),
        "received_at": result.get("received_at"),
        "category": result.get("category"),
        "priority": result.get("priority"),
        "confidence": result.get("confidence"),
        "confidence_level": result.get("confidence_level"),
        "confidence_source": result.get("confidence_source"),
        "classification_guardrail_flags": result.get("classification_guardrail_flags", []),
        "core_issue": result.get("core_issue"),
        "identifiers": result.get("identifiers", []),
        "urgency_signal": result.get("urgency_signal"),
        "proposed_queue": result.get("proposed_queue"),
        "destination_queue": result.get("destination_queue"),
        "escalation_flag": result.get("escalation_flag"),
        "escalation_rules_triggered": result.get("escalation_rules_triggered", []),
        "escalation_rule_evidence": result.get("escalation_rule_evidence", []),
        "escalation_reason": result.get("escalation_reason"),
        "human_summary": result.get("human_summary"),
        "timestamp": result.get("timestamp"),
    }


def write_summary(records: List[Dict[str, Any]]) -> None:
    """Write a concise markdown summary of submission records."""
    lines = [
        "# ArcVault Submission Summary",
        "",
        f"Total records: {len(records)}",
        "",
    ]

    for record in records:
        confidence = float(record.get("confidence") or 0.0)
        lines.append(
            f"- Sample {record['sample_id']}: "
            f"category={record['category']}, "
            f"confidence={confidence:.2f}, "
            f"proposed_queue={record['proposed_queue']}, "
            f"destination_queue={record['destination_queue']}, "
            f"escalation={record['escalation_flag']}"
        )

    SUBMISSION_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_submission_artifacts() -> Dict[str, str]:
    """Generate deterministic JSON + summary artifacts from the five samples."""
    # Reset replay tracking so deterministic submission runs do not inherit prior state.
    get_idempotency_store().clear()

    samples = load_samples()
    records: List[Dict[str, Any]] = []

    for sample in samples:
        result = process_message(sample["message"], sample["source"])
        records.append(build_submission_record(sample, result))

    records.sort(key=lambda item: item["sample_id"])

    if len(records) != 5:
        raise RuntimeError(f"Expected 5 submission records, received {len(records)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(SUBMISSION_JSON, "w", encoding="utf-8") as file_handle:
        json.dump(records, file_handle, indent=2, ensure_ascii=False)

    write_summary(records)

    return {
        "json_path": str(SUBMISSION_JSON),
        "summary_path": str(SUBMISSION_SUMMARY),
    }


def main() -> None:
    """CLI entry point for artifact generation."""
    paths = generate_submission_artifacts()
    print("Submission artifacts generated:")
    print(f"- JSON: {paths['json_path']}")
    print(f"- Summary: {paths['summary_path']}")


if __name__ == "__main__":
    main()
