"""
MQTT bridge for kwh-btc-iot.

- Subscribes to topics like: energy/<site_id>/<iot_device_id>/<meter_id>
- Parses JSON payload with fields:
    ts_start, ts_end, interval_s, energy_kwh, power_kw_avg, price_sats_per_kwh, status, tags
- Builds canonical JSON and POSTs it to /api/v1/logs on the gateway.

Usage (example):

    export MQTT_BROKER_HOST=localhost
    export MQTT_BROKER_PORT=1883
    export KWH_BTC_IOT_API=http://127.0.0.1:8000

    python -m mqtt_bridge

"""

import json
import os
import sys
from typing import Any, Dict

import paho.mqtt.client as mqtt
import requests


MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "energy/+/+/+")
API_BASE = os.getenv("KWH_BTC_IOT_API", "http://127.0.0.1:8000")


def build_canonical_log(topic: str, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    parts = topic.split("/")
    if len(parts) != 4 or parts[0] != "energy":
        raise ValueError(f"Unsupported topic format: {topic}")

    _, site_id, iot_device_id, meter_id = parts

    energy_kwh = float(payload_dict["energy_kwh"])
    price_sats_per_kwh = int(payload_dict["price_sats_per_kwh"])
    amount_sats = int(round(energy_kwh * price_sats_per_kwh))

    canonical = {
        "schema_version": "emlog-1.1",
        "site_id": site_id,
        "iot_device_id": iot_device_id,
        "meter_id": meter_id,
        "ts_start": payload_dict["ts_start"],
        "ts_end": payload_dict["ts_end"],
        "interval_s": payload_dict["interval_s"],
        "energy_kwh": energy_kwh,
        "power_kw_avg": payload_dict.get("power_kw_avg"),
        "status": payload_dict.get("status", "ok"),
        "tags": payload_dict.get("tags", []),
        "tx": {
            "unit": "sats",
            "price_sats_per_kwh": price_sats_per_kwh,
            "amount_sats": amount_sats,
            "channel": "ln",
            "settlement_status": "pending",
            "ln_invoice_id": None,
            "bitcoin_txid": None,
        },
    }
    return canonical


def on_connect(client, userdata, flags, rc):
    print(f"[mqtt_bridge] Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"[mqtt_bridge] Subscribed to {MQTT_TOPIC}")


def on_message(client, userdata, msg):
    try:
        payload_text = msg.payload.decode("utf-8")
        data = json.loads(payload_text)
        canonical = build_canonical_log(msg.topic, data)
        url = f"{API_BASE}/api/v1/logs"
        resp = requests.post(url, json=canonical, timeout=5)
        resp.raise_for_status()
        print(f"[mqtt_bridge] Posted log from topic {msg.topic}: {resp.json()['id']}")
    except Exception as exc:
        print(f"[mqtt_bridge] Error processing message on {msg.topic}: {exc}", file=sys.stderr)


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    print(f"[mqtt_bridge] Connecting to MQTT {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    client.loop_forever()


if __name__ == "__main__":
    main()
