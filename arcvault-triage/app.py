"""
ArcVault Support Triage System - Native web interface.

This module serves a FastAPI app that exposes:
- A browser UI built with plain HTML/CSS/JS
- JSON APIs for single-message triage and batch sample processing
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

# Load environment variables before importing workflow modules.
load_dotenv()

from workflow.graph import process_message


logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
SAMPLES_PATH = ROOT_DIR / "config" / "sample_inputs.json"

ALLOWED_SOURCES = ("Email", "Web Form", "Support Portal")


def load_samples() -> list[Dict[str, Any]]:
    """Load sample payloads used by the UI for prefill and batch QA."""
    if not SAMPLES_PATH.exists():
        return []
    with SAMPLES_PATH.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


SAMPLES = load_samples()


def _strip_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class TriageRequest(BaseModel):
    """Request payload accepted by the local UI API."""

    source: Literal["Email", "Web Form", "Support Portal"]
    message: str = Field(min_length=1, max_length=5000)
    request_id: Optional[str] = Field(default=None, max_length=128)
    external_id: Optional[str] = Field(default=None, max_length=128)
    customer_id: Optional[str] = Field(default=None, max_length=128)
    received_at: Optional[str] = None
    channel_metadata: Optional[Dict[str, Any]] = None

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("message must not be blank")
        return text

    @field_validator("request_id", "external_id", "customer_id")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _strip_optional_text(value)

    @field_validator("received_at")
    @classmethod
    def _validate_received_at(cls, value: Optional[str]) -> Optional[str]:
        value = _strip_optional_text(value)
        if value is None:
            return None
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("received_at must be ISO-8601") from exc
        return value


app = FastAPI(title="ArcVault Triage Console", version="1.2.0")
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _build_metadata(payload: TriageRequest) -> Dict[str, Any]:
    return {
        "request_id": payload.request_id or payload.external_id,
        "external_id": payload.external_id,
        "customer_id": payload.customer_id,
        "received_at": payload.received_at,
        "channel_metadata": payload.channel_metadata,
    }


@app.get("/health")
def health() -> Dict[str, str]:
    """Basic health endpoint for local checks."""
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """Serve the web UI."""
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="UI assets are missing.")
    return FileResponse(index_path)


@app.get("/api/samples")
def get_samples() -> Dict[str, Any]:
    """Return demo samples for UI prefill."""
    return {"samples": SAMPLES}


@app.post("/api/triage")
def triage(payload: TriageRequest) -> Dict[str, Any]:
    """Process one message through the triage workflow."""
    metadata = _build_metadata(payload)
    try:
        result = process_message(
            message=payload.message,
            source=payload.source,
            metadata=metadata,
        )
    except Exception as exc:  # pragma: no cover - integration behavior
        detail = str(exc) or "Processing failed."
        status_code = 502 if "Classification failed guardrails" in detail else 500
        if status_code == 502:
            logger.warning("Triage classification failed: %s", detail)
        else:
            logger.exception("Triage processing failed")
        raise HTTPException(status_code=status_code, detail=detail) from exc

    result["request_id"] = metadata["request_id"]
    result["external_id"] = payload.external_id
    result["customer_id"] = payload.customer_id
    result["received_at"] = payload.received_at
    result["channel_metadata"] = payload.channel_metadata
    return result


@app.post("/api/batch")
def batch_run() -> Dict[str, Any]:
    """Run triage against all configured samples and return concise results."""
    records: list[Dict[str, Any]] = []
    for sample in SAMPLES:
        metadata = sample.get("prefill") or {}
        try:
            result = process_message(
                message=sample.get("message", ""),
                source=sample.get("source", "Email"),
                metadata=metadata,
            )
            records.append(
                {
                    "sample_id": sample.get("id"),
                    "source": sample.get("source"),
                    "category": result.get("category"),
                    "priority": result.get("priority"),
                    "confidence": result.get("confidence"),
                    "confidence_level": result.get("confidence_level"),
                    "confidence_source": result.get("confidence_source"),
                    "destination_queue": result.get("destination_queue"),
                    "escalation_flag": result.get("escalation_flag"),
                    "idempotent_replay": result.get("idempotent_replay"),
                    "processing_ms": result.get("processing_ms"),
                }
            )
        except Exception as exc:  # pragma: no cover - integration behavior
            records.append(
                {
                    "sample_id": sample.get("id"),
                    "source": sample.get("source"),
                    "error": str(exc),
                }
            )

    return {"count": len(records), "records": records}


def main() -> None:
    """Run the local web server."""
    import uvicorn

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "7860"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run("app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
