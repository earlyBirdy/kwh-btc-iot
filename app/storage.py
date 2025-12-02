from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import EnergyLog, EnergyBatch

DB_PATH = Path(__file__).resolve().parent.parent / "kwh_btc_iot.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS energy_logs (
            id TEXT PRIMARY KEY,
            meter_id TEXT NOT NULL,
            site_id TEXT NOT NULL,
            iot_device_id TEXT NOT NULL,
            ts_start TEXT NOT NULL,
            ts_end TEXT NOT NULL,
            interval_s INTEGER NOT NULL,
            batch_id TEXT,
            leaf_hash TEXT NOT NULL,
            raw_json TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS energy_batches (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            log_count INTEGER NOT NULL,
            merkle_root TEXT NOT NULL,
            anchor_status TEXT NOT NULL,
            anchor_txid TEXT,
            anchor_block_hash TEXT,
            anchor_block_height INTEGER,
            anchor_block_time TEXT
        )
        """
    )

    conn.commit()
    conn.close()


_init_db()


class SQLiteStorage:
    """SQLite-backed storage for logs and batches."""

    # Logs -----

    def save_log(self, log: EnergyLog) -> None:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO energy_logs
            (id, meter_id, site_id, iot_device_id, ts_start, ts_end, interval_s,
             batch_id, leaf_hash, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log.id,
                log.meter_id,
                log.site_id,
                log.iot_device_id,
                log.ts_start.isoformat(),
                log.ts_end.isoformat(),
                log.interval_s,
                log.batch_id,
                log.leaf_hash,
                json.dumps(log.model_dump(), sort_keys=True),
            ),
        )
        conn.commit()
        conn.close()

    def list_logs(self) -> List[EnergyLog]:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM energy_logs ORDER BY ts_start ASC")
        rows = cur.fetchall()
        conn.close()
        return [self._log_from_row(r) for r in rows]

    def get_unbatched_logs(self) -> List[EnergyLog]:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM energy_logs WHERE batch_id IS NULL ORDER BY ts_start ASC"
        )
        rows = cur.fetchall()
        conn.close()
        return [self._log_from_row(r) for r in rows]

    def get_logs_by_ids(self, ids: List[str]) -> List[EnergyLog]:
        if not ids:
            return []
        conn = _get_conn()
        cur = conn.cursor()
        qmarks = ",".join("?" for _ in ids)
        cur.execute(
            f"SELECT * FROM energy_logs WHERE id IN ({qmarks}) ORDER BY ts_start ASC",
            ids,
        )
        rows = cur.fetchall()
        conn.close()
        return [self._log_from_row(r) for r in rows]

    def get_log(self, log_id: str) -> Optional[EnergyLog]:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM energy_logs WHERE id = ?", (log_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return self._log_from_row(row)

    def get_logs_by_batch(self, batch_id: str) -> List[EnergyLog]:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM energy_logs WHERE batch_id = ? ORDER BY ts_start ASC",
            (batch_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [self._log_from_row(r) for r in rows]

    def set_batch_for_logs(self, batch_id: str, log_ids: List[str]) -> None:
        if not log_ids:
            return
        conn = _get_conn()
        cur = conn.cursor()
        qmarks = ",".join("?" for _ in log_ids)
        cur.execute(
            f"UPDATE energy_logs SET batch_id = ? WHERE id IN ({qmarks})",
            [batch_id, *log_ids],
        )
        conn.commit()
        conn.close()

    # Batches -----

    def save_batch(self, batch: EnergyBatch) -> None:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO energy_batches
            (id, created_at, log_count, merkle_root,
             anchor_status, anchor_txid, anchor_block_hash,
             anchor_block_height, anchor_block_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.id,
                batch.created_at.isoformat(),
                batch.log_count,
                batch.merkle_root,
                batch.anchor_status,
                batch.anchor_txid,
                batch.anchor_block_hash,
                batch.anchor_block_height,
                batch.anchor_block_time.isoformat()
                if batch.anchor_block_time
                else None,
            ),
        )
        conn.commit()
        conn.close()

    def list_batches(self) -> List[EnergyBatch]:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM energy_batches ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        return [self._batch_from_row(r) for r in rows]

    def get_batch(self, batch_id: str) -> Optional[EnergyBatch]:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM energy_batches WHERE id = ?", (batch_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return self._batch_from_row(row)

    def update_batch_anchor(
        self,
        batch_id: str,
        anchor_status: str,
        anchor_txid: str,
        anchor_block_hash: str | None,
        anchor_block_height: int | None,
        anchor_block_time: datetime | None,
    ) -> Optional[EnergyBatch]:
        """Update anchor-related fields for a batch and return the updated object."""
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE energy_batches
            SET anchor_status = ?,
                anchor_txid = ?,
                anchor_block_hash = ?,
                anchor_block_height = ?,
                anchor_block_time = ?
            WHERE id = ?
            """,
            (
                anchor_status,
                anchor_txid,
                anchor_block_hash,
                anchor_block_height,
                anchor_block_time.isoformat() if anchor_block_time else None,
                batch_id,
            ),
        )
        conn.commit()
        conn.close()
        return self.get_batch(batch_id)

    # Row helpers -----

    def _log_from_row(self, row: sqlite3.Row) -> EnergyLog:
        data = json.loads(row["raw_json"])
        data.update(
            {
                "id": row["id"],
                "batch_id": row["batch_id"],
                "leaf_hash": row["leaf_hash"],
            }
        )
        return EnergyLog.model_validate(data)

    def _batch_from_row(self, row: sqlite3.Row) -> EnergyBatch:
        created_at = datetime.fromisoformat(row["created_at"])
        anchor_block_time = (
            datetime.fromisoformat(row["anchor_block_time"])
            if row["anchor_block_time"]
            else None
        )
        return EnergyBatch(
            id=row["id"],
            created_at=created_at,
            log_ids=[],  # derive via get_logs_by_batch if needed
            merkle_root=row["merkle_root"],
            log_count=row["log_count"],
            anchor_status=row["anchor_status"],
            anchor_txid=row["anchor_txid"],
            anchor_block_hash=row["anchor_block_hash"],
            anchor_block_height=row["anchor_block_height"],
            anchor_block_time=anchor_block_time,
        )


storage = SQLiteStorage()
