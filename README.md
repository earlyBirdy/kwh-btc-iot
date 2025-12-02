# kwh-btc-iot

**Energy (kWh) → Bitcoin (BTC/sats) → IoT (devices).**

`kwh-btc-iot` is a reference implementation of an **IoT-first energy logging gateway** that:

- Ingests **energy logs** from IoT devices (via HTTP; MQTT bridge optional)
- Normalizes them into a **canonical JSON** that includes both:
  - Physical energy usage (kWh, time window)
  - Economic view (sats per kWh, sats amount, settlement channel)
- Builds **Merkle trees** over logs and stores per-batch **Merkle roots**
- Exposes simple APIs for:
  - Pushing logs
  - Flushing a batch and getting its Merkle root
  - Fetching logs and basic Merkle proof info

This version stops at: **“Merkle root ready to be anchored”**.  
Hook it up later to Bitcoin Core / LND / Greenlight / external timestamp services.

---

## High-level Architecture

```text
IoT device (meter / gateway)
    |
    |  (MQTT or HTTP)
    v
+------------------------+
|  kwh-btc-iot gateway   |
|------------------------|
|  - Ingest energy logs  |
|  - Build canonical     |
|    energy+BTC JSON     |
|  - Compute leaf hash   |
|  - Store logs          |
|  - Batch logs          |
|  - Build Merkle root   |
+------------------------+
    |
    | (future)
    v
+------------------------+
|  Bitcoin stack         |
|  (Core / LND / etc.)   |
+------------------------+
```

**Canonical JSON per log (schema version `emlog-1.1`):**

```json
{
  "schema_version": "emlog-1.1",
  "site_id": "PLANT-01",
  "iot_device_id": "gw-PLANT01-003",
  "meter_id": "MTR-001",
  "ts_start": "2025-12-01T10:10:00Z",
  "ts_end": "2025-12-01T10:15:00Z",
  "interval_s": 300,
  "energy_kwh": 12.34,
  "power_kw_avg": 2.47,
  "status": "ok",
  "tags": ["peak"],
  "tx": {
    "unit": "sats",
    "price_sats_per_kwh": 100,
    "amount_sats": 1234,
    "channel": "ln",
    "settlement_status": "pending",
    "ln_invoice_id": null,
    "bitcoin_txid": null
  }
}
```

This JSON is serialized with sorted keys and hashed to form Merkle leaves.

---

## Quickstart

### 1. Install

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the API

```bash
uvicorn app.main:app --reload
```

Then open:

- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

---

## API Overview

### `POST /api/v1/logs`

Ingest a single energy+BTC log in canonical format.

Body example:

```json
{
  "schema_version": "emlog-1.1",
  "site_id": "PLANT-01",
  "iot_device_id": "gw-PLANT01-003",
  "meter_id": "MTR-001",
  "ts_start": "2025-12-01T10:10:00Z",
  "ts_end": "2025-12-01T10:15:00Z",
  "interval_s": 300,
  "energy_kwh": 12.34,
  "power_kw_avg": 2.47,
  "status": "ok",
  "tags": ["peak"],
  "tx": {
    "unit": "sats",
    "price_sats_per_kwh": 100,
    "amount_sats": 1234,
    "channel": "ln",
    "settlement_status": "pending",
    "ln_invoice_id": null,
    "bitcoin_txid": null
  }
}
```

The gateway will:

- Compute a deterministic `leaf_hash` from this JSON
- Persist the log in memory (for demo)
- Return an internal `log_id`

### `POST /api/v1/batches/flush`

Create a new Merkle batch from all unbatched logs.

Returns:

```json
{
  "batch_id": "batch_2025-12-01T10-10",
  "log_count": 10,
  "merkle_root": "a3f5...c9b2",
  "anchor_status": "pending"
}
```

### `GET /api/v1/logs`

List stored logs (demo, not paginated).

### `GET /api/v1/batches`

List existing batches.

---

## Folder Structure

```text
kwh-btc-iot/
  README.md
  requirements.txt
  app/
    __init__.py
    main.py          # FastAPI app and routes wiring
    models.py        # Pydantic models for logs and batches
    merkle.py        # Merkle tree building and verification
    storage.py       # Simple in-memory storage (replace with DB later)
    batching.py      # Batch building logic
  docs/
    architecture.md  # Textual architecture + diagrams
    datasets.md      # Dataset examples and MQTT mapping
  examples/
    mqtt_payload_example.json
    canonical_log_example.json
    batch_example.json
```

---

## Next Steps / Roadmap

- Replace in-memory storage with Postgres / SQLite
- Add MQTT bridge that:
  - Parses topics like `energy/<site_id>/<iot_device_id>/<meter_id>`
  - Builds canonical JSON and posts to `/api/v1/logs`
- Implement Merkle proofs per log
- Implement Bitcoin anchoring worker
  - Stores `anchor_txid`, `anchor_block_hash`, `anchor_block_height`
- Add basic web UI for browsing logs and batches


### SQLite backend & one-command Web UI

This repo now uses **SQLite** (`kwh_btc_iot.db` in the repo root) as the storage backend
and includes a minimal Web UI.

Run everything with a single command:

```bash
uvicorn app.main:app --reload
```

Then open:

- Web UI: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health


## New features

### Merkle proof endpoint

You can now retrieve a Merkle proof for any log that has been batched:

- **Endpoint:** `GET /api/v1/logs/{log_id}/proof`
- Returns:
  - `leaf_hash`
  - `merkle_root`
  - `batch_id`
  - `index` in the leaf list
  - `proof[]` (array of `{position, hash}` steps)

This is enough for an external verifier to recompute the path and confirm inclusion.

### MQTT bridge

A tiny MQTT bridge script is included:

- File: `mqtt_bridge.py`
- Subscribes to: `energy/<site_id>/<iot_device_id>/<meter_id>`
- Expects payload similar to `examples/mqtt_payload_example.json`
- Builds canonical emlog-1.1 JSON and `POST`s to `/api/v1/logs`.

Example usage:

```bash
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883
export KWH_BTC_IOT_API=http://127.0.0.1:8000

python mqtt_bridge.py
```

### Web UI sats columns

The Web UI at `/` now shows two extra columns in the Logs table:

- **Price (sats/kWh)**
- **Amount (sats)**

These are taken from the nested `tx` object returned by the API.
