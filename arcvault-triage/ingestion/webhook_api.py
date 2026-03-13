"""
FastAPI webhook ingestion service for ArcVault triage.

Endpoints:
- GET /health
- POST /intake

Features:
- Basic in-memory rate limiting (60 requests/minute)
- Pydantic input validation
"""

import time
from collections import deque
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from workflow.graph import process_message

# Rate limiting configuration
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 60
_request_timestamps: deque = deque()


class IntakeRequest(BaseModel):
    """Input payload for inbound support requests."""

    source: Literal["Email", "Web Form", "Support Portal"]
    message: str = Field(min_length=1)
    external_id: Optional[str] = None


app = FastAPI(title="ArcVault Intake API", version="1.0.0")


def _check_rate_limit() -> None:
    """Enforce simple in-memory rate limiting."""
    now = time.time()
    # Remove timestamps outside the window
    while _request_timestamps and _request_timestamps[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        _request_timestamps.popleft()
    if len(_request_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW_SECONDS}s.",
        )
    _request_timestamps.append(now)


@app.get("/health")
def health() -> dict:
    """Basic health endpoint for demo and monitoring checks."""
    return {"status": "ok"}


@app.post("/intake")
def intake(payload: IntakeRequest) -> dict:
    """
    Intake a support request and run triage automatically.

    Returns the processed triage record as JSON.
    """
    _check_rate_limit()

    try:
        result = process_message(payload.message, payload.source)
    except Exception as exc:  # pragma: no cover - integration behavior
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    if payload.external_id:
        result["external_id"] = payload.external_id

    return result

