# kwh-btc-iot Architecture

## Overview

`kwh-btc-iot` sits between **IoT devices** and a future **Bitcoin stack**:

```text
+------------------------+         +------------------------+
|   IoT devices          |         |   Bitcoin stack        |
|   - meters             |         |   - Core / LND / etc.  |
|   - gateways           |         +------------------------+
+------------+-----------+
             |
             | HTTP / (MQTT via bridge)
             v
+------------------------+
|   kwh-btc-iot          |
|------------------------|
| - Ingest canonical     |
|   energy+BTC logs      |
| - Compute leaf hash    |
| - Store logs           |
| - Batch logs           |
| - Build Merkle roots   |
+------------------------+
```

The gateway focuses on:

- **Canonical JSON logs** (energy + sats)
- **Merkle trees** for tamper-evident batches
- **Anchor-ready Merkle roots** (Bitcoin integration is a later step)

## Data Flow

```text
1. Device produces energy interval:
   - kWh used between ts_start and ts_end
   - Optional power average
   - Pricing in sats/kWh

2. Device (or bridge) sends log to /api/v1/logs as canonical JSON.

3. Gateway:
   - Serializes JSON with sorted keys
   - Computes leaf hash = SHA256("LOG::" + json_bytes)
   - Stores log + leaf hash

4. When requested (POST /api/v1/batches/flush):
   - Gateway gathers all unbatched logs
   - Builds Merkle tree over their leaf hashes
   - Computes Merkle root
   - Creates a batch record with:
     - batch_id
     - log_ids
     - merkle_root
     - anchor_status = pending

5. Later (out of scope for this repo version):
   - A worker anchors merkle_root to Bitcoin.
```

## Canonical Log Shape (emlog-1.1)

See `docs/datasets.md` for detailed examples.

The important part is:

- **Deterministic serialization** for hashing
- **Stable field names**
- **Consistent timestamp format (ISO-8601, UTC)**

## Storage

In this initial reference implementation, storage is:

- In-memory via `InMemoryStorage` class

You should replace this with a real database backend for real deployments (Postgres, SQLite, etc.) while keeping the same models:

- `EnergyLog`
- `EnergyBatch`
