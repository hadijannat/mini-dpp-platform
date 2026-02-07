"""
Merkle tree construction and inclusion proof verification.

Provides batch integrity verification by computing a single root hash from
a set of event hashes. Inclusion proofs allow verifying that a specific
event is part of a batch without replaying the entire tree.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def _hash_pair(left: str, right: str) -> str:
    """Hash two hex-encoded digests together (sorted for consistency)."""
    hasher = hashlib.sha256()
    hasher.update(left.encode("utf-8"))
    hasher.update(right.encode("utf-8"))
    return hasher.hexdigest()


def compute_merkle_root(hashes: list[str]) -> str:
    """Compute the Merkle root from a list of leaf hashes.

    If the list has an odd number of elements at any level, the last
    element is duplicated to form a complete pair.

    Parameters
    ----------
    hashes:
        List of hex-encoded SHA-256 hashes (the leaves).

    Returns
    -------
    str
        Hex-encoded SHA-256 Merkle root hash.

    Raises
    ------
    ValueError
        If ``hashes`` is empty.
    """
    if not hashes:
        raise ValueError("Cannot compute Merkle root from empty list")

    if len(hashes) == 1:
        return hashes[0]

    level = list(hashes)
    while len(level) > 1:
        next_level: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            next_level.append(_hash_pair(left, right))
        level = next_level

    return level[0]


def compute_inclusion_proof(hashes: list[str], index: int) -> list[tuple[str, str]]:
    """Compute an inclusion proof for the leaf at ``index``.

    The proof is a list of ``(sibling_hash, side)`` tuples where ``side``
    is ``"left"`` or ``"right"`` indicating which side the sibling sits on.

    Parameters
    ----------
    hashes:
        List of hex-encoded leaf hashes.
    index:
        Zero-based index of the target leaf.

    Returns
    -------
    list[tuple[str, str]]
        Proof path from leaf to root.

    Raises
    ------
    ValueError
        If ``hashes`` is empty or ``index`` is out of range.
    """
    if not hashes:
        raise ValueError("Cannot compute proof from empty list")
    if index < 0 or index >= len(hashes):
        raise ValueError(f"Index {index} out of range for {len(hashes)} hashes")

    if len(hashes) == 1:
        return []

    proof: list[tuple[str, str]] = []
    level = list(hashes)
    idx = index

    while len(level) > 1:
        next_level: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            next_level.append(_hash_pair(left, right))

        if idx % 2 == 0:
            sibling_idx = idx + 1
            if sibling_idx < len(level):
                proof.append((level[sibling_idx], "right"))
            else:
                proof.append((level[idx], "right"))
        else:
            proof.append((level[idx - 1], "left"))

        idx = idx // 2
        level = next_level

    return proof


def verify_inclusion_proof(
    leaf_hash: str,
    proof: list[tuple[str, str]],
    root: str,
) -> bool:
    """Verify that a leaf hash is included in a Merkle tree with the given root.

    Parameters
    ----------
    leaf_hash:
        Hex-encoded hash of the leaf to verify.
    proof:
        Inclusion proof as returned by ``compute_inclusion_proof()``.
    root:
        Expected Merkle root hash.

    Returns
    -------
    bool
        ``True`` if the proof is valid and the leaf is included.
    """
    current = leaf_hash
    for sibling_hash, side in proof:
        if side == "left":
            current = _hash_pair(sibling_hash, current)
        else:
            current = _hash_pair(current, sibling_hash)
    return current == root


@dataclass
class MerkleTree:
    """A Merkle tree built from a batch of event hashes.

    Attributes
    ----------
    leaves:
        The original leaf hashes.
    root:
        The computed Merkle root hash.
    """

    leaves: list[str] = field(default_factory=list)
    root: str = ""

    def __post_init__(self) -> None:
        if self.leaves and not self.root:
            self.root = compute_merkle_root(self.leaves)

    def inclusion_proof(self, index: int) -> list[tuple[str, str]]:
        """Return the inclusion proof for the leaf at ``index``."""
        return compute_inclusion_proof(self.leaves, index)

    def verify(self, leaf_hash: str, proof: list[tuple[str, str]]) -> bool:
        """Verify an inclusion proof against this tree's root."""
        return verify_inclusion_proof(leaf_hash, proof, self.root)

    @property
    def size(self) -> int:
        """Number of leaves in the tree."""
        return len(self.leaves)
