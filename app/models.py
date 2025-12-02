from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TxInfo(BaseModel):
    """Economic / Bitcoin view of an energy interval."""

    unit: str = Field(default="sats", description="Unit for pricing, e.g. sats.")
    price_sats_per_kwh: int = Field(..., ge=0, description="Price in sats per kWh.")
    amount_sats: int = Field(..., ge=0, description="Total amount in sats for this interval.")
    channel: str = Field(
        default="ln",
        description="Settlement channel: ln | onchain | internal.",
    )
    settlement_status: str = Field(
        default="pending",
        description="Settlement status: pending | settled | failed.",
    )
    ln_invoice_id: Optional[str] = Field(
        default=None, description="Lightning invoice identifier (if used)."
    )
    bitcoin_txid: Optional[str] = Field(
        default=None, description="Bitcoin transaction id (if on-chain)."
    )


class EnergyLogIn(BaseModel):
    """Canonical energy+BTC log (emlog-1.1).

    This is what clients submit to the API (or what the MQTT bridge builds).
    """

    schema_version: str = Field(default="emlog-1.1")

    site_id: str
    iot_device_id: str
    meter_id: str

    ts_start: datetime
    ts_end: datetime
    interval_s: int = Field(..., gt=0)

    energy_kwh: float = Field(..., ge=0.0)
    power_kw_avg: Optional[float] = Field(default=None)

    status: str = Field(default="ok", description="ok | estimated | error.")
    tags: List[str] = Field(default_factory=list)

    tx: TxInfo


class EnergyLog(EnergyLogIn):
    """Internal representation with gateway-assigned id, batch id and leaf hash."""

    id: str
    batch_id: Optional[str] = None
    leaf_hash: str


class EnergyBatch(BaseModel):
    """Batch of logs summarized by a Merkle root."""

    id: str
    created_at: datetime
    log_ids: List[str]
    merkle_root: str
    log_count: int
    anchor_status: str = "pending"
    anchor_txid: Optional[str] = None
    anchor_block_hash: Optional[str] = None
    anchor_block_height: Optional[int] = None
    anchor_block_time: Optional[datetime] = None
