"""Workflow nodes for the ArcVault Triage system."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from datetime import datetime
from typing import Any, Dict, List

from config.settings import (
    BILLING_DISPUTE_KEYWORDS,
    BILLING_ESCALATION_DELTA_THRESHOLD,
    CATEGORIES,
    ESCALATION_CONFIDENCE_THRESHOLD,
    ESCALATION_KEYWORDS,
    ESCALATION_QUEUE,
    PIPELINE_VERSION,
    PRIORITIES,
    QUEUE_MAPPING,
)
from integrations.gemini_client import get_gemini_client
from storage.idempotency_store import get_idempotency_store
from storage.record_store import append_record_jsonl
from workflow.prompts import CLASSIFICATION_PROMPT, ENRICHMENT_PROMPT
from workflow.state import TriageState


DEFAULT_CATEGORY = "Technical Question"
DEFAULT_PRIORITY = "Medium"
CONFIDENCE_HIGH_THRESHOLD = 0.85
CONFIDENCE_MEDIUM_THRESHOLD = 0.70

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _log_event(level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))


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

    if not math.isfinite(float(confidence)):
        confidence = default

    return max(0.0, min(1.0, float(confidence)))


def _parse_confidence(value: Any) -> float | None:
    """Parse confidence and enforce strict [0.0, 1.0] validation."""
    confidence = value
    if isinstance(confidence, str):
        confidence = confidence.strip()
        try:
            confidence = float(confidence)
        except ValueError:
            return None
    elif isinstance(confidence, (int, float)):
        confidence = float(confidence)
    else:
        return None

    if not math.isfinite(confidence):
        return None
    if confidence < 0.0 or confidence > 1.0:
        return None
    return float(confidence)


def _confidence_level(confidence: float) -> str:
    """Map confidence score to a display level."""
    if confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return "High"
    if confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def _canonicalize_message(message: str) -> str:
    """Normalize message text for stable deduplication."""
    return " ".join(message.split()).strip().lower()


def _build_dedup_key(source: str, message: str, request_id: str | None) -> str:
    """Build a persistent dedup key using request_id when available."""
    if request_id and request_id.strip():
        return f"request_id:{request_id.strip().lower()}"

    canonical = f"{source.strip().lower()}::{_canonicalize_message(message)}"
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"content:{content_hash}"


def _generate_record_id(dedup_key: str) -> str:
    """Generate a deterministic record ID from dedup key."""
    return hashlib.sha256(dedup_key.encode("utf-8")).hexdigest()[:16]


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


def _keyword_matches(message_lower: str, keyword: str) -> bool:
    """Check if a keyword matches using word boundaries."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, message_lower))


def _find_billing_dispute_keywords(message_lower: str) -> List[str]:
    matches: List[str] = []
    for keyword in BILLING_DISPUTE_KEYWORDS:
        if _keyword_matches(message_lower, keyword):
            matches.append(keyword)
    return matches


def _compute_processing_ms(started_at: Any) -> float:
    if isinstance(started_at, (int, float)):
        return round((time.perf_counter() - float(started_at)) * 1000.0, 2)
    return 0.0


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

    single_amount_rules = [
        rule.split(":", 1)[1]
        for rule in rules
        if rule.startswith("billing_single_amount_dispute:") and ":" in rule
    ]
    if single_amount_rules:
        amount = single_amount_rules[-1]
        parts.append(
            "Billing dispute language detected with one amount "
            f"(${amount}) requiring human review"
        )

    return "; ".join(parts)


def classify_node(state: TriageState) -> Dict[str, Any]:
    """
    Classify the message using Gemini API.

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
    except Exception as exc:  # pragma: no cover - integration behavior
        result = {}
        error_details = str(exc).strip().replace(",", ";").replace("\n", " ")
        if error_details:
            error_details = error_details[:220]
            classification_errors.append(
                f"classification_error:{exc.__class__.__name__}:{error_details}"
            )
        else:
            classification_errors.append(f"classification_error:{exc.__class__.__name__}")

    if not isinstance(result, dict):
        result = {}
        classification_errors.append("classification_error:non_dict_response")

    if any(flag.startswith("classification_error:") for flag in classification_errors):
        _log_event(
            logging.WARNING,
            "classification_guardrail_triggered",
            ingestion_id=state.get("ingestion_id"),
            flags=classification_errors,
            raw_result=result,
        )
        raise RuntimeError(
            "Classification failed guardrails: " + ", ".join(classification_errors)
        )

    category = result.get("category")

    # Normalize category (e.g., Incident -> Incident/Outage)
    if category == "Incident":
        category = "Incident/Outage"

    if category not in CATEGORIES:
        classification_errors.append(f"invalid_category:{category}")

    priority = result.get("priority")
    if priority not in PRIORITIES:
        classification_errors.append(f"invalid_priority:{priority}")

    confidence = _parse_confidence(result.get("confidence"))
    if confidence is None:
        classification_errors.append(f"invalid_confidence:{result.get('confidence')}")

    if classification_errors:
        _log_event(
            logging.WARNING,
            "classification_guardrail_triggered",
            ingestion_id=state.get("ingestion_id"),
            flags=classification_errors,
            raw_result=result,
        )
        raise RuntimeError(
            "Classification failed guardrails: " + ", ".join(classification_errors)
        )

    return {
        "category": category,
        "priority": priority,
        "confidence": float(confidence),
        "confidence_level": _confidence_level(float(confidence)),
        "confidence_source": "model",
        "classification_guardrail_flags": classification_errors,
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

    enrichment_errors: List[str] = []

    try:
        result = client.generate_json(prompt)
    except Exception as exc:  # pragma: no cover - integration behavior
        result = {}
        enrichment_errors.append(f"enrichment_error:{exc.__class__.__name__}")

    if not isinstance(result, dict):
        result = {}
        enrichment_errors.append("enrichment_error:non_dict_response")

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
        "enrichment_guardrail_flags": enrichment_errors,
    }


def route_node(state: TriageState) -> Dict[str, Any]:
    """
    Determine routing and escalation status.

    Escalation criteria:
    - Confidence below threshold
    - Escalation keywords in message
    - Billing issue with dollar amount delta above configured threshold
    - Billing issue with one amount + dispute language
    """
    category = state.get("category", DEFAULT_CATEGORY)
    proposed_queue = QUEUE_MAPPING.get(category, "IT/Security")

    confidence = _normalize_confidence(state.get("confidence", 1.0), default=1.0)
    message = state.get("message", "")
    message_lower = message.lower()

    escalation_rules_triggered: List[str] = []
    escalation_rule_evidence: List[str] = []

    if confidence < ESCALATION_CONFIDENCE_THRESHOLD:
        escalation_rules_triggered.append("low_confidence")
        escalation_rule_evidence.append(
            f"confidence={confidence:.2f}, threshold={ESCALATION_CONFIDENCE_THRESHOLD:.2f}"
        )

    for keyword in ESCALATION_KEYWORDS:
        if _keyword_matches(message_lower, keyword):
            escalation_rules_triggered.append(f"keyword:{keyword}")
            escalation_rule_evidence.append(f"matched_keyword='{keyword}'")

    if category == "Billing Issue":
        amounts = _extract_dollar_amounts(message)
        if len(amounts) >= 2:
            delta = max(amounts) - min(amounts)
            if delta > BILLING_ESCALATION_DELTA_THRESHOLD:
                escalation_rules_triggered.append(
                    f"billing_delta_exceeds_threshold:{delta:.2f}"
                )
                escalation_rule_evidence.append(
                    f"billing_amounts={amounts}, delta={delta:.2f}, "
                    f"threshold={BILLING_ESCALATION_DELTA_THRESHOLD:.2f}"
                )
        elif len(amounts) == 1:
            billing_dispute_hits = _find_billing_dispute_keywords(message_lower)
            if billing_dispute_hits:
                amount = amounts[0]
                escalation_rules_triggered.append(
                    f"billing_single_amount_dispute:{amount:.2f}"
                )
                escalation_rule_evidence.append(
                    f"billing_amount={amount:.2f}, dispute_keywords={billing_dispute_hits}"
                )

    escalation_flag = len(escalation_rules_triggered) > 0
    destination_queue = ESCALATION_QUEUE if escalation_flag else proposed_queue
    escalation_reason = _build_escalation_reason(escalation_rules_triggered, confidence)

    return {
        "proposed_queue": proposed_queue,
        "destination_queue": destination_queue,
        "escalation_flag": escalation_flag,
        "escalation_rules_triggered": escalation_rules_triggered,
        "escalation_rule_evidence": escalation_rule_evidence,
        "escalation_reason": escalation_reason,
    }


def output_node(state: TriageState) -> Dict[str, Any]:
    """
    Write the processed record to output destinations.

    This node writes:
    - Local JSONL runtime log (append-only, replay-safe)
    """
    timestamp = datetime.now().isoformat()
    request_id = state.get("request_id") or state.get("external_id")
    dedup_key = _build_dedup_key(
        state.get("source", ""),
        state.get("message", ""),
        request_id,
    )
    record_id = _generate_record_id(dedup_key)
    processing_ms = _compute_processing_ms(state.get("processing_started_at"))
    ingestion_id = state.get("ingestion_id")
    pipeline_version = state.get("pipeline_version", PIPELINE_VERSION)

    store = get_idempotency_store()
    is_replay = store.register_or_replay(
        dedup_key=dedup_key,
        record_id=record_id,
        source=state.get("source", ""),
        request_id=request_id,
    )

    response_meta = {
        "timestamp": timestamp,
        "record_id": record_id,
        "idempotent_replay": is_replay,
        "processing_ms": processing_ms,
        "ingestion_id": ingestion_id,
        "pipeline_version": pipeline_version,
    }

    if is_replay:
        _log_event(
            logging.INFO,
            "idempotent_replay_detected",
            ingestion_id=ingestion_id,
            record_id=record_id,
            dedup_key=dedup_key,
        )
        return {
            **response_meta,
            "output_saved": False,
            "sheets_saved": False,
            "sheets_status": "skipped:idempotent_replay",
            "sheets_error": None,
            "duplicate": True,
        }

    record = {
        "record_id": record_id,
        "timestamp": timestamp,
        "pipeline_version": pipeline_version,
        "ingestion_id": ingestion_id,
        "processing_ms": processing_ms,
        "idempotent_replay": False,
        "request_id": request_id,
        "external_id": state.get("external_id"),
        "customer_id": state.get("customer_id"),
        "received_at": state.get("received_at"),
        "channel_metadata": state.get("channel_metadata"),
        "source": state.get("source", ""),
        "message": state.get("message", ""),
        "category": state.get("category", ""),
        "priority": state.get("priority", ""),
        "confidence": _normalize_confidence(state.get("confidence", 0.0), default=0.0),
        "confidence_level": state.get("confidence_level")
        or _confidence_level(
            _normalize_confidence(state.get("confidence", 0.0), default=0.0)
        ),
        "confidence_source": state.get("confidence_source", "model"),
        "classification_guardrail_flags": state.get("classification_guardrail_flags", []),
        "enrichment_guardrail_flags": state.get("enrichment_guardrail_flags", []),
        "core_issue": state.get("core_issue", ""),
        "identifiers": state.get("identifiers", []),
        "urgency_signal": state.get("urgency_signal", ""),
        "proposed_queue": state.get("proposed_queue", ""),
        "destination_queue": state.get("destination_queue", ""),
        "escalation_flag": state.get("escalation_flag", False),
        "escalation_rules_triggered": state.get("escalation_rules_triggered", []),
        "escalation_rule_evidence": state.get("escalation_rule_evidence", []),
        "escalation_reason": state.get("escalation_reason"),
        "human_summary": state.get("human_summary", ""),
    }

    append_record_jsonl(record)

    _log_event(
        logging.INFO,
        "record_persisted",
        ingestion_id=ingestion_id,
        record_id=record_id,
        destination_queue=state.get("destination_queue"),
        escalation_flag=state.get("escalation_flag", False),
    )

    return {
        **response_meta,
        "output_saved": True,
        "record": record,  # Include record for background tasks
    }


def background_sheets_write(record: Dict[str, Any]) -> None:
    """Perform Google Sheets write in the background."""
    from integrations.sheets_client import get_sheets_client
    
    ingestion_id = record.get("ingestion_id")
    record_id = record.get("record_id")
    
    try:
        sheets_client = get_sheets_client()
        sheets_client.append_record(record)
        _log_event(
            logging.INFO,
            "sheets_write_success",
            ingestion_id=ingestion_id,
            record_id=record_id,
        )
    except Exception as exc:
        _log_event(
            logging.WARNING,
            "sheets_write_failed",
            ingestion_id=ingestion_id,
            record_id=record_id,
            error=str(exc),
        )


def escalate_node(state: TriageState) -> Dict[str, Any]:
    """
    Handle escalated messages that need human review.

    This node performs output operations and logs an explicit escalation alert.
    """
    result = output_node(state)
    result["escalation_processed"] = True
    result["escalation_reason"] = state.get("escalation_reason")

    _log_event(
        logging.WARNING,
        "escalation_alert",
        ingestion_id=state.get("ingestion_id"),
        record_id=result.get("record_id"),
        category=state.get("category"),
        priority=state.get("priority"),
        proposed_queue=state.get("proposed_queue"),
        destination_queue=state.get("destination_queue"),
        rules=state.get("escalation_rules_triggered", []),
        reason=state.get("escalation_reason"),
    )
    return result
