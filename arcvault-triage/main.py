#!/usr/bin/env python3
"""
ArcVault Triage System - CLI Entry Point.

This module provides a command-line interface for processing messages
through the triage workflow.
"""

import argparse
import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from workflow.graph import process_message


def load_samples() -> List[Dict[str, Any]]:
    """Load sample inputs from config file."""
    config_path = os.path.join(os.path.dirname(__file__), "config", "sample_inputs.json")
    with open(config_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def print_header() -> None:
    """Print CLI header."""
    print("\n" + "=" * 72)
    print("ArcVault Support Triage System")
    print("=" * 72)


def print_result(result: Dict[str, Any]) -> None:
    """Pretty print a processing result."""
    print("\n" + "-" * 72)
    print(f"Category:          {result.get('category', 'N/A')}")
    print(f"Priority:          {result.get('priority', 'N/A')}")
    print(f"Confidence:        {result.get('confidence', 0):.2%}")
    print(f"Proposed Queue:    {result.get('proposed_queue', 'N/A')}")
    print(f"Final Queue:       {result.get('destination_queue', 'N/A')}")

    escalation = result.get("escalation_flag", False)
    if escalation:
        rules = result.get("escalation_rules_triggered", [])
        rules_text = ", ".join(rules) if rules else "N/A"
        print(f"Escalation:        YES")
        print(f"Escalation Rules:  {rules_text}")
        print(f"Escalation Reason: {result.get('escalation_reason', 'Unknown')}")
    else:
        print("Escalation:        No")

    print(f"\nCore Issue: {result.get('core_issue', 'N/A')}")
    print(f"Identifiers: {', '.join(result.get('identifiers', [])) or 'None'}")
    print(f"\nSummary: {result.get('human_summary', 'N/A')}")
    print("-" * 72)


def process_single(message: str, source: str) -> Optional[Dict[str, Any]]:
    """Process a single message."""
    print_header()
    print(f"\nProcessing message from {source}...")
    preview = message[:100] + "..." if len(message) > 100 else message
    print(f"Message: {preview}")

    try:
        result = process_message(message, source)
        print_result(result)
        return result
    except Exception as exc:  # pragma: no cover - integration behavior
        print(f"\nError: {exc}")
        return None


def process_all_samples() -> List[Dict[str, Any]]:
    """Process all sample messages."""
    print_header()
    print("\nProcessing all sample messages...\n")

    samples = load_samples()
    results: List[Dict[str, Any]] = []

    for index, sample in enumerate(samples, 1):
        print(f"\n[{index}/{len(samples)}] Processing sample {sample['id']}...")
        try:
            result = process_message(sample["message"], sample["source"])
            results.append(result)
            print_result(result)
        except Exception as exc:  # pragma: no cover - integration behavior
            print(f"[ERROR] Error processing sample {sample['id']}: {exc}")

    print("\n" + "=" * 72)
    print(f"[DONE] Processed {len(results)}/{len(samples)} messages successfully")
    print("=" * 72)

    return results


def run_submission_artifacts() -> None:
    """Generate deterministic submission artifacts for all sample inputs."""
    from scripts.generate_submission_artifacts import generate_submission_artifacts

    print_header()
    print("\nGenerating deterministic submission artifacts...")
    paths = generate_submission_artifacts()

    print("\nSubmission files generated:")
    print(f"- JSON:    {paths['json_path']}")
    print(f"- Summary: {paths['summary_path']}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="ArcVault Support Triage CLI")
    subparsers = parser.add_subparsers(dest="command")

    parser_all = subparsers.add_parser("all", help="Process all sample messages")
    parser_all.add_argument(
        "--submission",
        action="store_true",
        help="Generate deterministic submission artifacts instead of runtime append log",
    )

    parser_sample = subparsers.add_parser("sample", help="Process a specific sample")
    parser_sample.add_argument("number", type=int, help="Sample number (1-5)")

    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    if args.command in (None, "all"):
        if getattr(args, "submission", False):
            run_submission_artifacts()
        else:
            process_all_samples()
        return

    if args.command == "sample":
        samples = load_samples()
        sample_num = args.number
        if 1 <= sample_num <= len(samples):
            sample = samples[sample_num - 1]
            process_single(sample["message"], sample["source"])
        else:
            print(f"Invalid sample number. Use 1-{len(samples)}")


if __name__ == "__main__":
    main()
