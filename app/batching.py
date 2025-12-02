from __future__ import annotations

from datetime import datetime
from typing import Tuple, List

from .models import EnergyBatch, EnergyLog
from .merkle import build_merkle_root
from .storage import storage


def flush_batch(now: datetime | None = None) -> Tuple[EnergyBatch, List[EnergyLog]]:
    """Create a new batch from all unbatched logs.

    Returns the new batch and the list of logs that were included.
    """
    logs = storage.get_unbatched_logs()
    if not logs:
        raise ValueError("No unbatched logs available")

    now = now or datetime.utcnow()
    batch_id = now.strftime("batch_%Y-%m-%dT%H-%M-%S")

    leaves = [log.leaf_hash for log in logs]
    merkle_root = build_merkle_root(leaves)

    log_ids = [log.id for log in logs]
    batch = EnergyBatch(
        id=batch_id,
        created_at=now,
        log_ids=log_ids,
        merkle_root=merkle_root,
        log_count=len(log_ids),
        anchor_status="pending",
    )

    storage.save_batch(batch)
    storage.set_batch_for_logs(batch_id, log_ids)

    return batch, logs
