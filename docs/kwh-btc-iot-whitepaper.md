
# kWh-BTC-IoT White Paper

## 1. Introduction
As global infrastructure electrifies, energy becomes the primary economic unit that powers machines, factories, EVs, robotics, and microgrids. However, energy lacks a native digital settlement layer. Bitcoin, grounded in verifiable energy expenditure, offers a globally neutral, programmable unit of account capable of M2M settlement.

kWh-BTC-IoT establishes a trustless energy accounting and settlement system linking IoT metering, Merkle proofs, and Bitcoin anchoring.

## 2. Problem
Energy systems today suffer from:
- Unverifiable metering and billing
- Closed SCADA/EMS platforms
- Vendor-locked audit trails
- Poor cross-tenant transparency
- Lack of real-time, machine-readable settlement

## 3. Solution Architecture
### 3.1 IoT Ingestion
Meters publish MQTT messages: `energy/<site>/<device>/<meter>`.
Gateways convert payloads into canonical `emlog-1.1` energy+BTC logs.

### 3.2 Integrity and Merkle Trees
Every log → leaf hash → batched Merkle root.
Each log gains a verifiable inclusion proof.

### 3.3 Bitcoin Anchoring
Merkle roots can be:
- Published on Bitcoin L1 (OP_RETURN)
- Settled through Lightning (sats/kWh)
- Exported for external anchoring workflows

### 3.4 Storage and APIs
SQLite-backed storage with FastAPI:
- `/api/v1/logs`
- `/api/v1/batches/flush`
- `/api/v1/logs/{log_id}/proof`
- `/api/v1/batches/{batch_id}/export`

### 3.5 Web UI
Dashboard features:
- kWh/day/device
- sats/day/device
- Log explorer
- Batch explorer
- Anchor simulator

## 4. Use Cases
- Factory-level cost allocation
- Data center tenant energy settlement
- Microgrid P2P energy trading
- Autonomous EV charging payment
- Robotic fleet charging

## 5. Why Bitcoin?
Bitcoin acts as the global settlement network for machine-to-machine commerce:
- Final settlement
- Neutral access
- Micro-payments
- Global timestamping

## 6. Conclusion
kWh-BTC-IoT provides the foundation for trustless, energy-native machine economies, enabling new markets in autonomous power negotiation, auditability, and settlement.
