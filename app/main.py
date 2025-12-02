from __future__ import annotations

import json
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from uuid import uuid4

from .models import EnergyLogIn, EnergyLog, EnergyBatch
from .merkle import leaf_hash_from_payload
from .storage import storage
from .batching import flush_batch as flush_batch_logic


app = FastAPI(
    title="kwh-btc-iot",
    description="IoT-first energy+BTC logging gateway with Merkle batching (SQLite backend).",
    version="1.2.0",
)


class HealthResponse(BaseModel):
    status: str
    time: datetime


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", time=datetime.utcnow())


@app.get("/", response_class=HTMLResponse)
def web_ui() -> str:
    """Very simple web UI (single page) showing logs and batches.

    One-command experience:
        uvicorn app.main:app --reload
    and then open http://127.0.0.1:8000/
    """
    return """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>kwh-btc-iot – Web UI</title>
    <style>
      body { font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; }
      h1, h2 { margin-bottom: 0.3rem; }
      table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; margin-bottom: 1.5rem; }
      th, td { border: 1px solid #ccc; padding: 4px 6px; font-size: 0.85rem; }
      th { background: #f5f5f5; text-align: left; }
      button { padding: 6px 10px; margin-right: 8px; cursor: pointer; }
      .toolbar { margin-bottom: 1rem; }
      .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; }
      .badge-ok { background: #e0f7e9; color: #146c2e; }
      .badge-pending { background: #fff8e1; color: #8a6d1f; }
    </style>
  </head>
  <body>
    <h1>kwh-btc-iot</h1>
    <p>SQLite-backed energy+BTC log gateway with Merkle batching.</p>

    <div class="toolbar">
      <button onclick="flushBatch()">Flush batch (Merkle)</button>
      <button onclick="reloadAll()">Reload</button>
      <span id="status"></span>
    </div>

    <h2>Logs</h2>
    <div id="logs"></div>

    <h2>Batches</h2>
    <div id="batches"></div>

    <script>
      async function fetchJSON(url, options) {
        const res = await fetch(url, options || {});
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || res.statusText);
        }
        return res.json();
      }

      function fmtTs(ts) {
        if (!ts) return "";
        try {
          return new Date(ts).toLocaleString();
        } catch {
          return ts;
        }
      }

      function setStatus(msg, isError) {
        const el = document.getElementById("status");
        el.textContent = msg;
        el.style.color = isError ? "red" : "#333";
      }

      async function loadLogs() {
        const container = document.getElementById("logs");
        container.innerHTML = "Loading...";
        try {
          const data = await fetchJSON("/api/v1/logs");
          if (!data.length) {
            container.innerHTML = "<em>No logs yet.</em>";
            return;
          }
          let html = "<table><thead><tr>" +
            "<th>ID</th><th>Site</th><th>Device</th><th>Meter</th>" +
            "<th>Start</th><th>End</th><th>kWh</th><th>Status</th><th>Batch</th>" +
            "</tr></thead><tbody>";
          for (const log of data) {
            const statusBadge = `<span class='badge badge-ok'>${log.status}</span>`;
            html += "<tr>" +
              `<td>${log.id}</td>` +
              `<td>${log.site_id}</td>` +
              `<td>${log.iot_device_id}</td>` +
              `<td>${log.meter_id}</td>` +
              `<td>${fmtTs(log.ts_start)}</td>` +
              `<td>${fmtTs(log.ts_end)}</td>` +
              `<td>${log.energy_kwh}</td>` +
              `<td>${statusBadge}</td>` +
              `<td>${log.batch_id || ""}</td>` +
              "</tr>";
          }
          html += "</tbody></table>";
          container.innerHTML = html;
        } catch (err) {
          container.innerHTML = "<span style='color:red'>Error loading logs</span>";
          console.error(err);
        }
      }

      async function loadBatches() {
        const container = document.getElementById("batches");
        container.innerHTML = "Loading...";
        try {
          const data = await fetchJSON("/api/v1/batches");
          if (!data.length) {
            container.innerHTML = "<em>No batches yet.</em>";
            return;
          }
          let html = "<table><thead><tr>" +
            "<th>ID</th><th>Created</th><th>Log count</th>" +
            "<th>Merkle root</th><th>Anchor status</th>" +
            "</tr></thead><tbody>";
          for (const b of data) {
            const statusBadge = `<span class='badge badge-pending'>${b.anchor_status}</span>`;
            html += "<tr>" +
              `<td>${b.id}</td>` +
              `<td>${fmtTs(b.created_at)}</td>` +
              `<td>${b.log_count}</td>` +
              `<td style='font-family:monospace;font-size:0.75rem'>${b.merkle_root}</td>` +
              `<td>${statusBadge}</td>` +
              "</tr>";
          }
          html += "</tbody></table>";
          container.innerHTML = html;
        } catch (err) {
          container.innerHTML = "<span style='color:red'>Error loading batches</span>";
          console.error(err);
        }
      }

      async function flushBatch() {
        try {
          setStatus("Flushing batch...", false);
          await fetchJSON("/api/v1/batches/flush", { method: "POST" });
          setStatus("Batch created.", false);
          await loadLogs();
          await loadBatches();
        } catch (err) {
          console.error(err);
          setStatus("Error flushing batch: " + err.message, true);
        }
      }

      async function reloadAll() {
        await loadLogs();
        await loadBatches();
        setStatus("Reloaded.", false);
      }

      reloadAll();
    </script>
  </body>
</html>
"""


@app.post("/api/v1/logs", response_model=EnergyLog)
def create_log(payload: EnergyLogIn) -> EnergyLog:
    """Ingest a canonical energy+BTC log."""
    log_id = f"log_{uuid4().hex[:12]}"

    json_bytes = json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    leaf = leaf_hash_from_payload(json_bytes)

    log = EnergyLog(id=log_id, leaf_hash=leaf, **payload.model_dump())
    storage.save_log(log)
    return log


@app.get("/api/v1/logs", response_model=List[EnergyLog])
def list_logs() -> List[EnergyLog]:
    """List all logs."""
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
    """List all batches."""
    return storage.list_batches()
