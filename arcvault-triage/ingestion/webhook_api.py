"""FastAPI webhook ingestion service for ArcVault triage."""

from __future__ import annotations

import os
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from config.settings import (
    MAX_CHANNEL_METADATA_KEYS,
    MAX_CUSTOMER_ID_LENGTH,
    MAX_EXTERNAL_ID_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_REQUEST_ID_LENGTH,
)
from workflow.graph import process_message

# Rate limiting configuration
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 60
_request_timestamps: deque = deque()

# Optional authentication. If unset, endpoint remains open for demo mode.
INTAKE_API_KEY_ENV = "INTAKE_API_KEY"


class IntakeRequest(BaseModel):
    """Input payload for inbound support requests."""

    source: Literal["Email", "Web Form", "Support Portal"]
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    request_id: Optional[str] = Field(default=None, max_length=MAX_REQUEST_ID_LENGTH)
    customer_id: Optional[str] = Field(default=None, max_length=MAX_CUSTOMER_ID_LENGTH)
    received_at: Optional[datetime] = None
    channel_metadata: Optional[Dict[str, Any]] = None
    external_id: Optional[str] = Field(default=None, max_length=MAX_EXTERNAL_ID_LENGTH)

    @field_validator("message")
    @classmethod
    def _normalize_message(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("message must not be blank")
        return text

    @field_validator("request_id", "customer_id", "external_id")
    @classmethod
    def _strip_optional_ids(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("channel_metadata")
    @classmethod
    def _validate_channel_metadata(
        cls,
        value: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if len(value) > MAX_CHANNEL_METADATA_KEYS:
            raise ValueError(
                f"channel_metadata supports up to {MAX_CHANNEL_METADATA_KEYS} keys"
            )
        return value


app = FastAPI(title="ArcVault Intake API", version="1.1.0")


def _check_rate_limit() -> None:
    """Enforce simple in-memory rate limiting."""
    now = time.time()
    # Remove timestamps outside the window.
    while _request_timestamps and _request_timestamps[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        _request_timestamps.popleft()
    if len(_request_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. Max {RATE_LIMIT_MAX_REQUESTS} requests per "
                f"{RATE_LIMIT_WINDOW_SECONDS}s."
            ),
        )
    _request_timestamps.append(now)


def _enforce_api_key(request: Request) -> None:
    """Optionally enforce X-API-Key when INTAKE_API_KEY is configured."""
    expected_api_key = os.getenv(INTAKE_API_KEY_ENV)
    if not expected_api_key:
        return

    provided = request.headers.get("X-API-Key")
    if not provided:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    if provided != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")


@app.get("/health")
def health() -> dict:
    """Basic health endpoint for demo and monitoring checks."""
    return {"status": "ok"}


@app.post("/intake")
def intake(payload: IntakeRequest, request: Request) -> dict:
    """
    Intake a support request and run triage automatically.

    Returns the processed triage record as JSON.
    """
    _check_rate_limit()
    _enforce_api_key(request)

    ingestion_id = str(uuid.uuid4())
    request_id = payload.request_id or payload.external_id

    metadata: Dict[str, Any] = {
        "ingestion_id": ingestion_id,
        "request_id": request_id,
        "external_id": payload.external_id,
        "customer_id": payload.customer_id,
        "received_at": payload.received_at.isoformat() if payload.received_at else None,
        "channel_metadata": payload.channel_metadata,
    }

    try:
        result = process_message(payload.message, payload.source, metadata=metadata)
    except Exception as exc:  # pragma: no cover - integration behavior
        detail = str(exc) or "Processing failed."
        status_code = 502 if "Classification failed guardrails" in detail else 500
        raise HTTPException(status_code=status_code, detail=detail) from exc

    result["ingestion_id"] = ingestion_id
    result["request_id"] = request_id
    if payload.external_id:
        result["external_id"] = payload.external_id
    if payload.customer_id:
        result["customer_id"] = payload.customer_id
    if payload.received_at:
        result["received_at"] = payload.received_at.isoformat()
    if payload.channel_metadata is not None:
        result["channel_metadata"] = payload.channel_metadata

    return result
