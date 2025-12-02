from __future__ import annotations

import json
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from uuid import uuid4

from .models import EnergyLogIn, EnergyLog, EnergyBatch
from .merkle import leaf_hash_from_payload
from .storage import storage
from .batching import flush_batch as flush_batch_logic


app = FastAPI(
    title="kwh-btc-iot",
    description="IoT-first energy+BTC logging gateway with Merkle batching.",
    version="1.1.0",
)


class HealthResponse(BaseModel):
    status: str
    time: datetime


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", time=datetime.utcnow())


@app.post("/api/v1/logs", response_model=EnergyLog)
def create_log(payload: EnergyLogIn) -> EnergyLog:
    """Ingest a canonical energy+BTC log.

    The client can be:
    - a direct HTTP producer, or
    - an MQTT bridge that has already assembled the canonical JSON.
    """
    log_id = f"log_{uuid4().hex[:12]}"

    # Serialize deterministically for hashing.
    json_bytes = json.dumps(
        payload.model_dump(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    leaf = leaf_hash_from_payload(json_bytes)

    log = EnergyLog(id=log_id, leaf_hash=leaf, **payload.model_dump())
    storage.save_log(log)
    return log


@app.get("/api/v1/logs", response_model=List[EnergyLog])
def list_logs() -> List[EnergyLog]:
    """List all logs (demo only, no paging)."""
    return storage.list_logs()


@app.post("/api/v1/batches/flush", response_model=EnergyBatch)
def flush_batch() -> EnergyBatch:
    """Make a new Merkle batch from all unbatched logs."""
    try:
        batch, _logs = flush_batch_logic()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return batch


@app.get("/api/v1/batches", response_model=List[EnergyBatch])
def list_batches() -> List[EnergyBatch]:
    return storage.list_batches()
