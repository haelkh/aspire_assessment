"""
Optional live smoke test for one real Gemini-backed run.

Usage:
    python scripts/smoke_live_api.py
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from workflow.graph import process_message


load_dotenv()


def main() -> None:
    """Run a single live smoke test using sample 1."""
    root = Path(__file__).resolve().parents[1]
    samples_path = root / "config" / "sample_inputs.json"

    with open(samples_path, "r", encoding="utf-8") as file_handle:
        samples = json.load(file_handle)

    sample = samples[0]
    result = process_message(sample["message"], sample["source"])

    print("Live smoke test passed.")
    print(f"Category: {result.get('category')}")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Final Queue: {result.get('destination_queue')}")
    print(f"Escalation: {result.get('escalation_flag')}")


if __name__ == "__main__":
    main()

