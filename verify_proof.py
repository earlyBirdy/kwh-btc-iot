"""
CLI Merkle proof verifier for kwh-btc-iot.

Usage:

    # Save proof JSON from GET /api/v1/logs/{log_id}/proof:
    curl http://127.0.0.1:8000/api/v1/logs/<log_id>/proof > proof.json

    # Verify:
    python verify_proof.py proof.json

Exit code:
    0 = proof is valid
    1 = proof is invalid / error
"""

import json
import sys
from pathlib import Path

from app.merkle import verify_merkle_proof


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python verify_proof.py <proof.json>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to parse JSON: {exc}", file=sys.stderr)
        return 1

    leaf_hash = data.get("leaf_hash")
    merkle_root = data.get("merkle_root")
    proof = data.get("proof")

    if not (leaf_hash and merkle_root and isinstance(proof, list)):
        print("Invalid proof JSON: missing leaf_hash / merkle_root / proof[]", file=sys.stderr)
        return 1

    ok = verify_merkle_proof(leaf_hash, merkle_root, proof)
    if ok:
        print("✅ Merkle proof is VALID for the given root.")
        return 0
    else:
        print("❌ Merkle proof is INVALID for the given root.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
