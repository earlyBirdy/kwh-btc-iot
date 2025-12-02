# Datasets for kwh-btc-iot

This document summarizes the key dataset shapes used by `kwh-btc-iot`.

## 1. Canonical Energy+BTC Log (emlog-1.1)

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

- `energy_kwh` – energy used in the interval
- `price_sats_per_kwh` – price applied (sats per kWh)
- `amount_sats` – `energy_kwh * price_sats_per_kwh` (back-end can compute)
- `channel` – `ln` (Lightning), `onchain`, or `internal`
- `settlement_status` – settlement lifecycle; Bitcoin anchoring is separate

## 2. Example MQTT Payload vs Canonical JSON

If you use an MQTT bridge, a device might publish:

- Topic: `energy/PLANT-01/gw-PLANT01-003/MTR-001`
- Payload:

```json
{
  "ts_start": "2025-12-01T10:10:00Z",
  "ts_end": "2025-12-01T10:15:00Z",
  "interval_s": 300,
  "energy_kwh": 12.34,
  "power_kw_avg": 2.47,
  "price_sats_per_kwh": 100,
  "status": "ok",
  "tags": ["peak"]
}
```

The bridge can then assemble the canonical JSON by injecting:

- `site_id`
- `iot_device_id`
- `meter_id`
- computing `amount_sats`

## 3. Batch Representation

```json
{
  "id": "batch_2025-12-01T10-10-00",
  "created_at": "2025-12-01T10:16:00Z",
  "log_ids": [
    "log_a1b2c3d4e5f6",
    "log_0123456789ab"
  ],
  "merkle_root": "a3f5...c9b2",
  "log_count": 2,
  "anchor_status": "pending",
  "anchor_txid": null,
  "anchor_block_hash": null,
  "anchor_block_height": null,
  "anchor_block_time": null
}
```

This batch is ready to be anchored to Bitcoin, but the act of anchoring and updating the `anchor_*` fields is out of scope for this first repo version.
