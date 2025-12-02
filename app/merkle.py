import hashlib
from typing import List, Dict, Literal

HashHex = str
Position = Literal["left", "right"]
ProofStep = Dict[str, str]


def sha256_hex(data: bytes) -> HashHex:
    return hashlib.sha256(data).hexdigest()


def leaf_hash_from_payload(payload: bytes) -> HashHex:
    """Hash canonical JSON payload for a log.

    A simple domain separator is used so we can distinguish
    between different tree types in the future.
    """
    return sha256_hex(b"LOG::" + payload)


def build_merkle_root(leaves: List[HashHex]) -> HashHex:
    """Build a Merkle root from a list of leaf hashes (hex-encoded)."""
    if not leaves:
        return "0" * 64

    level = leaves[:]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        next_level: List[HashHex] = []
        for i in range(0, len(level), 2):
            combined = bytes.fromhex(level[i]) + bytes.fromhex(level[i + 1])
            next_level.append(sha256_hex(combined))
        level = next_level

    return level[0]


def build_merkle_proof(leaves: List[HashHex], index: int) -> List[ProofStep]:
    """Return the Merkle path for leaf at `index`."""
    if index < 0 or index >= len(leaves):
        raise IndexError("Leaf index out of range")

    if not leaves:
        return []

    level = leaves[:]
    proof: List[ProofStep] = []
    idx = index

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        next_level: List[HashHex] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1]

            if i == idx or i + 1 == idx:
                if idx == i:
                    proof.append({"position": "right", "hash": right})
                else:
                    proof.append({"position": "left", "hash": left})

                parent = sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))
                next_level.append(parent)
                idx = len(next_level) - 1
            else:
                parent = sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))
                next_level.append(parent)

        level = next_level

    return proof


def verify_merkle_proof(leaf: HashHex, root: HashHex, proof: List[ProofStep]) -> bool:
    """Verify a Merkle proof against a given root."""
    current = leaf
    for step in proof:
        position: Position = step["position"]  # type: ignore
        sibling = step["hash"]
        if position == "left":
            current = sha256_hex(bytes.fromhex(sibling) + bytes.fromhex(current))
        elif position == "right":
            current = sha256_hex(bytes.fromhex(current) + bytes.fromhex(sibling))
        else:
            raise ValueError(f"Invalid proof position: {position}")
    return current == root
