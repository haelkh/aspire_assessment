"""
ArcVault Support Triage System - Gradio Web Interface.

This module provides a web-based UI for the triage system using Gradio.
Run this file to start the web interface.
"""

import json
import os
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

# Load environment variables FIRST, before importing any LangChain/LangGraph modules
load_dotenv()

import gradio as gr

from workflow.graph import process_message


def load_samples() -> List[Dict[str, Any]]:
    """Load sample inputs from JSON file."""
    config_path = os.path.join(os.path.dirname(__file__), "config", "sample_inputs.json")
    with open(config_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


SAMPLES = load_samples()


def process_single_message(source: str, message: str) -> Tuple[Dict[str, Any], str]:
    """
    Process a single message through the triage workflow.

    Returns:
        Tuple of (results_dict, status_message).
    """
    if not message or not message.strip():
        return {}, "Please enter a message to process."

    if not source:
        return {}, "Please select a message source."

    try:
        result = process_message(message, source)

        display_result = {
            "Category": result.get("category", "Unknown"),
            "Priority": result.get("priority", "Unknown"),
            "Confidence": f"{result.get('confidence', 0):.2%}",
            "Guardrail Flags": result.get("classification_guardrail_flags", []),
            "Proposed Queue": result.get("proposed_queue", "Unknown"),
            "Final Queue": result.get("destination_queue", "Unknown"),
            "Escalation": "YES" if result.get("escalation_flag") else "NO",
            "Escalation Rules": result.get("escalation_rules_triggered", []),
            "Escalation Evidence": result.get("escalation_rule_evidence", []),
            "Escalation Reason": result.get("escalation_reason") or "N/A",
            "Core Issue": result.get("core_issue", "N/A"),
            "Identifiers": ", ".join(result.get("identifiers", [])) or "None found",
            "Urgency Signal": result.get("urgency_signal", "None"),
            "Summary": result.get("human_summary", "N/A"),
            "Timestamp": result.get("timestamp", "N/A"),
            "Ingestion ID": result.get("ingestion_id", "N/A"),
            "Pipeline Version": result.get("pipeline_version", "N/A"),
            "Processing (ms)": result.get("processing_ms", 0.0),
            "Idempotent Replay": result.get("idempotent_replay", False),
        }

        status = "Message processed successfully."
        if result.get("escalation_flag"):
            status = "Message processed and routed to Human Review."

        return display_result, status

    except Exception as exc:  # pragma: no cover - integration behavior
        return {}, f"Error processing message: {exc}"


def load_sample(sample_id: int) -> Tuple[str, str]:
    """Load a sample message into the form."""
    if 1 <= sample_id <= len(SAMPLES):
        sample = SAMPLES[sample_id - 1]
        return sample["source"], sample["message"]
    return "", ""


def batch_process_all() -> Tuple[str, str]:
    """Process all sample messages and return a formatted markdown summary."""
    lines = ["## Batch Results\n"]

    for index, sample in enumerate(SAMPLES, 1):
        try:
            result = process_message(sample["message"], sample["source"])
            escalation = "🚨 YES" if result.get("escalation_flag") else "✅ NO"
            lines.append(
                f"### Sample {index} ({sample['source']})\n"
                f"| Field | Value |\n"
                f"|---|---|\n"
                f"| Category | {result.get('category')} |\n"
                f"| Priority | {result.get('priority')} |\n"
                f"| Confidence | {result.get('confidence', 0):.2%} |\n"
                f"| Proposed Queue | {result.get('proposed_queue')} |\n"
                f"| Final Queue | {result.get('destination_queue')} |\n"
                f"| Escalation | {escalation} |\n"
                f"| Core Issue | {result.get('core_issue')} |\n"
                f"| Summary | {result.get('human_summary')} |\n"
            )
        except Exception as exc:  # pragma: no cover - integration behavior
            lines.append(f"### Sample {index}: ❌ Error — {exc}\n")

    full_summary = "\n".join(lines)
    return full_summary, f"Processed {len(SAMPLES)} samples."


with gr.Blocks(
    title="ArcVault Triage System",
) as demo:
    gr.Markdown(
        """
        # ArcVault Support Triage System

        AI-powered intake and triage pipeline for customer support messages.
        """
    )

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("## Input")

            source_dropdown = gr.Dropdown(
                choices=["Email", "Web Form", "Support Portal"],
                label="Message Source",
                value="Email",
                interactive=True,
            )

            message_textbox = gr.Textbox(
                lines=5,
                label="Message Content",
                placeholder="Paste the customer message here...",
                interactive=True,
            )

            with gr.Row():
                process_btn = gr.Button("Process Message", variant="primary", size="lg")
                clear_btn = gr.Button("Clear", variant="secondary")

            gr.Markdown("### Load Sample Messages")
            with gr.Row():
                sample1_btn = gr.Button("Sample 1", size="sm")
                sample2_btn = gr.Button("Sample 2", size="sm")
                sample3_btn = gr.Button("Sample 3", size="sm")
            with gr.Row():
                sample4_btn = gr.Button("Sample 4", size="sm")
                sample5_btn = gr.Button("Sample 5", size="sm")
                batch_btn = gr.Button("Process All Samples", variant="secondary", size="sm")

        with gr.Column(scale=3):
            gr.Markdown("## Results")

            status_output = gr.Textbox(label="Status", interactive=False, lines=1)
            results_json = gr.JSON(label="Processed Record", height=420)
            batch_output = gr.Markdown(label="Batch Results", visible=False)

    process_btn.click(
        fn=process_single_message,
        inputs=[source_dropdown, message_textbox],
        outputs=[results_json, status_output],
    )

    clear_btn.click(
        fn=lambda: ("Email", "", {}, ""),
        outputs=[source_dropdown, message_textbox, results_json, status_output],
    )

    sample1_btn.click(fn=lambda: load_sample(1), outputs=[source_dropdown, message_textbox])
    sample2_btn.click(fn=lambda: load_sample(2), outputs=[source_dropdown, message_textbox])
    sample3_btn.click(fn=lambda: load_sample(3), outputs=[source_dropdown, message_textbox])
    sample4_btn.click(fn=lambda: load_sample(4), outputs=[source_dropdown, message_textbox])
    sample5_btn.click(fn=lambda: load_sample(5), outputs=[source_dropdown, message_textbox])

    def run_batch() -> Tuple[str, str, Any]:
        summary, status = batch_process_all()
        return summary, status, gr.update(visible=True)

    batch_btn.click(
        fn=run_batch,
        outputs=[batch_output, status_output, batch_output],
    )

    gr.Markdown(
        """
        ---
        Results are saved to `output/processed_records.jsonl` and Google Sheets (if configured).
        """
    )


def main() -> None:
    """Launch the Gradio web interface."""
    print("=" * 60)
    print("ArcVault Support Triage System")
    print("=" * 60)
    print("\nStarting web interface...")
    print("Open your browser to: http://localhost:7860")
    print("\nPress Ctrl+C to stop the server.")
    print("=" * 60)

    demo.launch(
        server_name="localhost",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
