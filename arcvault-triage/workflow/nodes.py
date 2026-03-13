"""
Workflow nodes for the ArcVault Triage system.

This module contains the node functions that process messages
through the triage pipeline using LangGraph.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from workflow.state import TriageState
from workflow.prompts import CLASSIFICATION_PROMPT, ENRICHMENT_PROMPT
from integrations.gemini_client import get_gemini_client
from config.settings import (
    BILLING_ESCALATION_DELTA_THRESHOLD,
    CATEGORIES,
    ESCALATION_CONFIDENCE_THRESHOLD,
    ESCALATION_KEYWORDS,
    ESCALATION_QUEUE,
    PRIORITIES,
    QUEUE_MAPPING,
)


DEFAULT_CATEGORY = "Technical Question"
DEFAULT_PRIORITY = "Medium"


def _normalize_confidence(value: Any, default: float = 0.5) -> float:
    """Normalize a confidence value to a float in [0.0, 1.0]."""
    confidence = value
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except ValueError:
            confidence = default
    elif not isinstance(confidence, (int, float)):
        confidence = default

    return max(0.0, min(1.0, float(confidence)))


def _extract_dollar_amounts(message: str) -> List[float]:
    """Extract dollar-denominated monetary amounts from free text."""
    matches = re.findall(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", message)
    amounts: List[float] = []

    for match in matches:
        try:
            amounts.append(float(match.replace(",", "")))
        except ValueError:
            continue

    return amounts


def _build_escalation_reason(rules: List[str], confidence: float) -> str | None:
    """Build a readable escalation reason from machine-readable rules."""
    if not rules:
        return None

    parts: List[str] = []

    if "low_confidence" in rules:
        parts.append(
            f"Low confidence score: {confidence:.2f} < {ESCALATION_CONFIDENCE_THRESHOLD:.2f}"
        )

    keyword_hits = [
        rule.split(":", 1)[1]
        for rule in rules
        if rule.startswith("keyword:") and ":" in rule
    ]
    if keyword_hits:
        parts.append(f"Escalation keywords detected: {', '.join(keyword_hits)}")

    billing_rules = [
        rule.split(":", 1)[1]
        for rule in rules
        if rule.startswith("billing_delta_exceeds_threshold:") and ":" in rule
    ]
    if billing_rules:
        delta = billing_rules[-1]
        parts.append(
            "Billing amount delta exceeds threshold "
            f"({delta} > {BILLING_ESCALATION_DELTA_THRESHOLD:.2f})"
        )

    return "; ".join(parts)


def classify_node(state: TriageState) -> Dict[str, Any]:
    """
    Classify the message using Gemini API.

    This node analyzes the message and assigns:
    - category: The type of request (Bug Report, Feature Request, etc.)
    - priority: Urgency level (Low, Medium, High)
    - confidence: How certain the model is about the classification

    Invalid or failed LLM outputs are sanitized and forced into
    escalation-safe defaults.
    """
    client = get_gemini_client()
    prompt = CLASSIFICATION_PROMPT.format(
        message=state["message"],
        source=state["source"],
    )

    classification_errors: List[str] = []

    try:
        result = client.generate_json(prompt)
    except Exception as exc:  # pragma: no cover - exercised via integration/smoke paths
        result = {}
        classification_errors.append(f"classification_error:{exc.__class__.__name__}")

    if not isinstance(result, dict):
        result = {}
        classification_errors.append("classification_error:non_dict_response")

    category = result.get("category", DEFAULT_CATEGORY)
    if category not in CATEGORIES:
        classification_errors.append(f"invalid_category:{category}")
        category = DEFAULT_CATEGORY

    priority = result.get("priority", DEFAULT_PRIORITY)
    if priority not in PRIORITIES:
        classification_errors.append(f"invalid_priority:{priority}")
        priority = DEFAULT_PRIORITY

    confidence = _normalize_confidence(result.get("confidence", 0.5), default=0.5)

    # Any validation failure forces escalation-safe confidence.
    if classification_errors:
        confidence = 0.0

    return {
        "category": category,
        "priority": priority,
        "confidence": confidence,
    }


def enrich_node(state: TriageState) -> Dict[str, Any]:
    """
    Enrich the message with extracted information.

    This node never raises on malformed model output and always returns
    a complete, usable payload.
    """
    client = get_gemini_client()

    prompt = ENRICHMENT_PROMPT.format(
        message=state["message"],
        category=state["category"],
        priority=state["priority"],
    )

    try:
        result = client.generate_json(prompt)
    except Exception:  # pragma: no cover - exercised via integration/smoke paths
        result = {}

    if not isinstance(result, dict):
        result = {}

    core_issue = str(
        result.get("core_issue")
        or "Customer submitted a support request that requires human review."
    )
    identifiers = result.get("identifiers", [])

    if isinstance(identifiers, str):
        identifiers = [identifiers] if identifiers.strip() else []
    elif not isinstance(identifiers, list):
        identifiers = []

    normalized_identifiers: List[str] = []
    for identifier in identifiers:
        text = str(identifier).strip()
        if text:
            normalized_identifiers.append(text)

    urgency_signal = str(result.get("urgency_signal") or "None")
    human_summary = str(
        result.get("human_summary")
        or "The model could not fully enrich this message. "
        "Please review the raw message and triage manually."
    )

    return {
        "core_issue": core_issue,
        "identifiers": normalized_identifiers,
        "urgency_signal": urgency_signal,
        "human_summary": human_summary,
    }


def route_node(state: TriageState) -> Dict[str, Any]:
    """
    Determine routing and escalation status.

    Escalation criteria:
    - Confidence below threshold
    - Escalation keywords in message
    - Billing issue with dollar amount delta above configured threshold
    """
    category = state.get("category", DEFAULT_CATEGORY)
    proposed_queue = QUEUE_MAPPING.get(category, "IT/Security")

    confidence = _normalize_confidence(state.get("confidence", 1.0), default=1.0)
    message_lower = state.get("message", "").lower()

    escalation_rules_triggered: List[str] = []

    if confidence < ESCALATION_CONFIDENCE_THRESHOLD:
        escalation_rules_triggered.append("low_confidence")

    matched_keywords: List[str] = []
    for keyword in ESCALATION_KEYWORDS:
        if keyword.lower() in message_lower:
            matched_keywords.append(keyword)
            escalation_rules_triggered.append(f"keyword:{keyword}")

    if category == "Billing Issue":
        amounts = _extract_dollar_amounts(state.get("message", ""))
        if len(amounts) >= 2:
            delta = max(amounts) - min(amounts)
            if delta > BILLING_ESCALATION_DELTA_THRESHOLD:
                escalation_rules_triggered.append(
                    f"billing_delta_exceeds_threshold:{delta:.2f}"
                )

    escalation_flag = len(escalation_rules_triggered) > 0
    destination_queue = ESCALATION_QUEUE if escalation_flag else proposed_queue
    escalation_reason = _build_escalation_reason(escalation_rules_triggered, confidence)

    return {
        "proposed_queue": proposed_queue,
        "destination_queue": destination_queue,
        "escalation_flag": escalation_flag,
        "escalation_rules_triggered": escalation_rules_triggered,
        "escalation_reason": escalation_reason,
    }


def output_node(state: TriageState) -> Dict[str, Any]:
    """
    Write the processed record to output destinations.

    This node writes:
    - Local JSON runtime log (append-only)
    - Google Sheets row (if configured)
    """
    from integrations.sheets_client import get_sheets_client

    timestamp = datetime.now().isoformat()

    record = {
        "timestamp": timestamp,
        "source": state.get("source", ""),
        "message": state.get("message", ""),
        "category": state.get("category", ""),
        "priority": state.get("priority", ""),
        "confidence": state.get("confidence", 0.0),
        "core_issue": state.get("core_issue", ""),
        "identifiers": state.get("identifiers", []),
        "urgency_signal": state.get("urgency_signal", ""),
        "proposed_queue": state.get("proposed_queue", state.get("destination_queue", "")),
        "destination_queue": state.get("destination_queue", ""),
        "escalation_flag": state.get("escalation_flag", False),
        "escalation_rules_triggered": state.get("escalation_rules_triggered", []),
        "escalation_reason": state.get("escalation_reason"),
        "human_summary": state.get("human_summary", ""),
    }

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "processed_records.json")

    existing_records: List[Dict[str, Any]] = []
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as file_handle:
                existing_records = json.load(file_handle)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_records = []

    existing_records.append(record)

    with open(output_file, "w", encoding="utf-8") as file_handle:
        json.dump(existing_records, file_handle, indent=2, ensure_ascii=False)

    try:
        sheets_client = get_sheets_client()
        sheets_client.append_record(record)
        sheets_success = True
    except Exception as exc:
        print(f"Warning: Could not write to Google Sheets: {exc}")
        sheets_success = False

    return {
        "timestamp": timestamp,
        "output_saved": True,
        "sheets_saved": sheets_success,
    }


def escalate_node(state: TriageState) -> Dict[str, Any]:
    """
    Handle escalated messages that need human review.

    This node performs output operations and logs an explicit escalation alert.
    """
    result = output_node(state)

    result["escalation_processed"] = True
    result["escalation_reason"] = state.get("escalation_reason")

    print(f"\n{'=' * 60}")
    print("ESCALATION ALERT")
    print(f"{'=' * 60}")
    print(f"Category: {state.get('category')}")
    print(f"Priority: {state.get('priority')}")
    print(f"Proposed Queue: {state.get('proposed_queue')}")
    print(f"Final Queue: {state.get('destination_queue')}")
    print(f"Reason: {state.get('escalation_reason')}")
    print(f"Core Issue: {state.get('core_issue')}")
    print(f"{'=' * 60}\n")

    return result
