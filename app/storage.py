from __future__ import annotations

from typing import Dict, List, Optional

from .models import EnergyLog, EnergyBatch


class InMemoryStorage:
    """Simple storage backend for demo and tests.

    Replace with a real database for production use.
    """

    def __init__(self) -> None:
        self._logs: Dict[str, EnergyLog] = {}
        self._batches: Dict[str, EnergyBatch] = {}

    # Logs

    def save_log(self, log: EnergyLog) -> None:
        self._logs[log.id] = log

    def list_logs(self) -> List[EnergyLog]:
        return list(self._logs.values())

    def get_unbatched_logs(self) -> List[EnergyLog]:
        return [l for l in self._logs.values() if l.batch_id is None]

    def get_logs_by_ids(self, ids: List[str]) -> List[EnergyLog]:
        return [self._logs[i] for i in ids if i in self._logs]

    def set_batch_for_logs(self, batch_id: str, log_ids: List[str]) -> None:
        for log_id in log_ids:
            if log_id in self._logs:
                log = self._logs[log_id]
                log.batch_id = batch_id
                self._logs[log_id] = log

    # Batches

    def save_batch(self, batch: EnergyBatch) -> None:
        self._batches[batch.id] = batch

    def list_batches(self) -> List[EnergyBatch]:
        return list(self._batches.values())

    def get_batch(self, batch_id: str) -> Optional[EnergyBatch]:
        return self._batches.get(batch_id)


storage = InMemoryStorage()
