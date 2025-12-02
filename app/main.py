from __future__ import annotations

import json
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from uuid import uuid4

from .models import EnergyLogIn, EnergyLog, EnergyBatch
from .merkle import leaf_hash_from_payload, build_merkle_root, build_merkle_proof
from .storage import storage
from .batching import flush_batch as flush_batch_logic


app = FastAPI(
    title="kwh-btc-iot",
    description="IoT-first energy+BTC logging gateway with Merkle batching (SQLite backend).",
    version="1.5.0",
)


class HealthResponse(BaseModel):
    status: str
    time: datetime


class MerkleProofStep(BaseModel):
    position: Literal["left", "right"]
    hash: str


class MerkleProofResponse(BaseModel):
    log_id: str
    batch_id: str
    leaf_hash: str
    merkle_root: str
    index: int
    proof: List[MerkleProofStep]


class BatchExportResponse(BaseModel):
    batch: EnergyBatch
    logs: List[EnergyLog]


class AnchorSimulateRequest(BaseModel):
    txid: Optional[str] = None
    block_hash: Optional[str] = None
    block_height: Optional[int] = None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", time=datetime.utcnow())


@app.get("/", response_class=HTMLResponse)
def web_ui() -> str:
    """Web UI: logs, batches, and a simple kWh → sats dashboard."""
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
      .badge-anchored { background: #e3f2fd; color: #0d47a1; }
      .mono { font-family: monospace; font-size: 0.75rem; }
      .section { margin-top: 2rem; }
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

    <div class="section">
      <h2>Dashboard – kWh → sats (per day & device)</h2>
      <div id="dashboard"></div>
    </div>

    <div class="section">
      <h2>Logs</h2>
      <div id="logs"></div>
    </div>

    <div class="section">
      <h2>Batches</h2>
      <div id="batches"></div>
    </div>

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

      function dateOnly(ts) {
        if (!ts) return "";
        try {
          const d = new Date(ts);
          const y = d.getFullYear();
          const m = String(d.getMonth() + 1).padStart(2, "0");
          const day = String(d.getDate()).padStart(2, "0");
          return `${y}-${m}-${day}`;
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
            "<th>Start</th><th>End</th><th>kWh</th>" +
            "<th>Price (sats/kWh)</th><th>Amount (sats)</th>" +
            "<th>Status</th><th>Batch</th>" +
            "</tr></thead><tbody>";
          for (const log of data) {
            const statusBadge = `<span class='badge badge-ok'>${log.status}</span>`;
            const price = log.tx ? log.tx.price_sats_per_kwh : "";
            const amount = log.tx ? log.tx.amount_sats : "";
            html += "<tr>" +
              `<td>${log.id}</td>` +
              `<td>${log.site_id}</td>` +
              `<td>${log.iot_device_id}</td>` +
              `<td>${log.meter_id}</td>` +
              `<td>${fmtTs(log.ts_start)}</td>` +
              `<td>${fmtTs(log.ts_end)}</td>` +
              `<td>${log.energy_kwh}</td>` +
              `<td>${price}</td>` +
              `<td>${amount}</td>` +
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
            "<th>Merkle root</th><th>Anchor status</th><th>TXID</th>" +
            "<th>Actions</th>" +
            "</tr></thead><tbody>";
          for (const b of data) {
            let badgeClass = "badge-pending";
            if (b.anchor_status === "anchored") {
              badgeClass = "badge-anchored";
            }
            const statusBadge = `<span class='badge ${badgeClass}'>${b.anchor_status}</span>`;
            const txid = b.anchor_txid || "";
            html += "<tr>" +
              `<td>${b.id}</td>` +
              `<td>${fmtTs(b.created_at)}</td>` +
              `<td>${b.log_count}</td>` +
              `<td class='mono'>${b.merkle_root}</td>` +
              `<td>${statusBadge}</td>` +
              `<td class='mono'>${txid}</td>` +
              `<td><button onclick="simulateAnchor('${b.id}')">Sim anchor</button></td>` +
              "</tr>";
          }
          html += "</tbody></table>";
          container.innerHTML = html;
        } catch (err) {
          container.innerHTML = "<span style='color:red'>Error loading batches</span>";
          console.error(err);
        }
      }

      async function loadDashboard() {
        const container = document.getElementById("dashboard");
        container.innerHTML = "Loading...";
        try {
          const data = await fetchJSON("/api/v1/logs");
          if (!data.length) {
            container.innerHTML = "<em>No logs yet.</em>";
            return;
          }
          const agg = {};
          for (const log of data) {
            const day = dateOnly(log.ts_start);
            const dev = log.iot_device_id;
            const key = day + "||" + dev;
            if (!agg[key]) {
              agg[key] = {
                day,
                device: dev,
                energy_kwh: 0,
                amount_sats: 0,
              };
            }
            agg[key].energy_kwh += Number(log.energy_kwh || 0);
            if (log.tx && typeof log.tx.amount_sats === "number") {
              agg[key].amount_sats += log.tx.amount_sats;
            }
          }
          const rows = Object.values(agg).sort((a, b) => {
            if (a.day < b.day) return -1;
            if (a.day > b.day) return 1;
            if (a.device < b.device) return -1;
            if (a.device > b.device) return 1;
            return 0;
          });
          let html = "<table><thead><tr>" +
            "<th>Day</th><th>Device</th>" +
            "<th>Total kWh</th><th>Total sats</th>" +
            "</tr></thead><tbody>";
          for (const r of rows) {
            html += "<tr>" +
              `<td>${r.day}</td>` +
              `<td>${r.device}</td>` +
              `<td>${r.energy_kwh.toFixed(3)}</td>` +
              `<td>${r.amount_sats}</td>` +
              "</tr>";
          }
          html += "</tbody></table>";
          container.innerHTML = html;
        } catch (err) {
          container.innerHTML = "<span style='color:red'>Error building dashboard</span>";
          console.error(err);
        }
      }

      async function flushBatch() {
        try {
          setStatus("Flushing batch...", false);
          await fetchJSON("/api/v1/batches/flush", { method: "POST" });
          setStatus("Batch created.", false);
          await reloadAll();
        } catch (err) {
          console.error(err);
          setStatus("Error flushing batch: " + err.message, true);
        }
      }

      async function simulateAnchor(batchId) {
        try {
          setStatus("Simulating anchor for " + batchId + "...", false);
          await fetchJSON(`/api/v1/batches/${batchId}/anchor/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          setStatus("Anchor simulated for " + batchId, false);
          await loadBatches();
        } catch (err) {
          console.error(err);
          setStatus("Error simulating anchor: " + err.message, true);
        }
      }

      async function reloadAll() {
        await loadDashboard();
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

    json_bytes = json.dumps(
        payload.model_dump(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
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


@app.get("/api/v1/logs/{log_id}/proof", response_model=MerkleProofResponse)
def get_log_proof(log_id: str) -> MerkleProofResponse:
    """Return Merkle proof for a given log_id (if batched)."""
    log = storage.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    if not log.batch_id:
        raise HTTPException(
            status_code=400, detail="Log has not been assigned to a batch yet"
        )

    batch = storage.get_batch(log.batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    batch_logs = storage.get_logs_by_batch(log.batch_id)
    leaf_list = [l.leaf_hash for l in batch_logs]

    try:
        index = [l.id for l in batch_logs].index(log_id)
    except ValueError:
        raise HTTPException(
            status_code=500, detail="Log not found in its own batch"
        ) from None

    recomputed_root = build_merkle_root(leaf_list)
    if recomputed_root != batch.merkle_root:
        raise HTTPException(
            status_code=500,
            detail="Merkle root mismatch for batch; stored root may be inconsistent",
        )

    proof_steps_raw = build_merkle_proof(leaf_list, index)
    proof_steps = [MerkleProofStep(**s) for s in proof_steps_raw]

    return MerkleProofResponse(
        log_id=log_id,
        batch_id=log.batch_id,
        leaf_hash=log.leaf_hash,
        merkle_root=batch.merkle_root,
        index=index,
        proof=proof_steps,
    )


@app.get("/api/v1/batches/{batch_id}/export", response_model=BatchExportResponse)
def export_batch(batch_id: str) -> BatchExportResponse:
    """Export a batch plus its logs as JSON for external anchoring tools."""
    batch = storage.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    logs = storage.get_logs_by_batch(batch_id)
    return BatchExportResponse(batch=batch, logs=logs)


@app.post("/api/v1/batches/{batch_id}/anchor/simulate", response_model=EnergyBatch)
def simulate_anchor(batch_id: str, body: AnchorSimulateRequest) -> EnergyBatch:
    """Anchor simulator: write fake txid & block info to show full lifecycle."""
    batch = storage.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    now = datetime.utcnow()
    txid = body.txid or f"simtx_{batch_id}"
    block_hash = body.block_hash or f"simblock_{batch_id}"
    block_height = body.block_height or 100000

    updated = storage.update_batch_anchor(
        batch_id=batch_id,
        anchor_status="anchored",
        anchor_txid=txid,
        anchor_block_hash=block_hash,
        anchor_block_height=block_height,
        anchor_block_time=now,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update batch anchor info")
    return updated
