"""
FastAPI webhook ingestion service for ArcVault triage.

Endpoints:
- GET /health
- POST /intake
"""

from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from workflow.graph import process_message


class IntakeRequest(BaseModel):
    """Input payload for inbound support requests."""

    source: Literal["Email", "Web Form", "Support Portal"]
    message: str = Field(min_length=1)
    external_id: Optional[str] = None


app = FastAPI(title="ArcVault Intake API", version="1.0.0")


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
    try:
        result = process_message(payload.message, payload.source)
    except Exception as exc:  # pragma: no cover - integration behavior
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    if payload.external_id:
        result["external_id"] = payload.external_id

    return result

