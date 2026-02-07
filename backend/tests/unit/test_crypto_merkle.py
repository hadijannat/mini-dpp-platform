"""Tests for crypto Merkle tree module."""

from __future__ import annotations

import hashlib

import pytest

from app.core.crypto.merkle import (
    MerkleTree,
    compute_inclusion_proof,
    compute_merkle_root,
    verify_inclusion_proof,
)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


class TestComputeMerkleRoot:
    """Tests for Merkle root computation."""

    def test_single_leaf(self) -> None:
        h = _sha256_hex("leaf0")
        root = compute_merkle_root([h])
        assert root == h

    def test_two_leaves(self) -> None:
        h0 = _sha256_hex("leaf0")
        h1 = _sha256_hex("leaf1")
        root = compute_merkle_root([h0, h1])
        # Manually compute expected
        expected = hashlib.sha256((h0 + h1).encode()).hexdigest()
        assert root == expected

    def test_four_leaves(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(4)]
        root = compute_merkle_root(leaves)
        assert isinstance(root, str)
        assert len(root) == 64

    def test_odd_number_of_leaves(self) -> None:
        """Odd leaves: last element is duplicated."""
        leaves = [_sha256_hex(f"leaf{i}") for i in range(3)]
        root = compute_merkle_root(leaves)
        assert isinstance(root, str)
        assert len(root) == 64

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_merkle_root([])

    def test_deterministic(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(5)]
        r1 = compute_merkle_root(leaves)
        r2 = compute_merkle_root(leaves)
        assert r1 == r2

    def test_order_matters(self) -> None:
        h0 = _sha256_hex("a")
        h1 = _sha256_hex("b")
        r1 = compute_merkle_root([h0, h1])
        r2 = compute_merkle_root([h1, h0])
        assert r1 != r2


class TestInclusionProof:
    """Tests for Merkle inclusion proof computation and verification."""

    def test_two_leaves_proof_index_0(self) -> None:
        h0 = _sha256_hex("leaf0")
        h1 = _sha256_hex("leaf1")
        root = compute_merkle_root([h0, h1])
        proof = compute_inclusion_proof([h0, h1], 0)
        assert len(proof) == 1
        assert proof[0] == (h1, "right")
        assert verify_inclusion_proof(h0, proof, root)

    def test_two_leaves_proof_index_1(self) -> None:
        h0 = _sha256_hex("leaf0")
        h1 = _sha256_hex("leaf1")
        root = compute_merkle_root([h0, h1])
        proof = compute_inclusion_proof([h0, h1], 1)
        assert len(proof) == 1
        assert proof[0] == (h0, "left")
        assert verify_inclusion_proof(h1, proof, root)

    def test_four_leaves_all_indices(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(4)]
        root = compute_merkle_root(leaves)
        for i in range(4):
            proof = compute_inclusion_proof(leaves, i)
            assert verify_inclusion_proof(leaves[i], proof, root)

    def test_eight_leaves_all_indices(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(8)]
        root = compute_merkle_root(leaves)
        for i in range(8):
            proof = compute_inclusion_proof(leaves, i)
            assert verify_inclusion_proof(leaves[i], proof, root)

    def test_odd_leaves_all_indices(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(5)]
        root = compute_merkle_root(leaves)
        for i in range(5):
            proof = compute_inclusion_proof(leaves, i)
            assert verify_inclusion_proof(leaves[i], proof, root)

    def test_single_leaf_empty_proof(self) -> None:
        h = _sha256_hex("solo")
        proof = compute_inclusion_proof([h], 0)
        assert proof == []
        assert verify_inclusion_proof(h, proof, h)

    def test_wrong_leaf_fails(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(4)]
        root = compute_merkle_root(leaves)
        proof = compute_inclusion_proof(leaves, 0)
        wrong_leaf = _sha256_hex("wrong")
        assert not verify_inclusion_proof(wrong_leaf, proof, root)

    def test_wrong_root_fails(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(4)]
        compute_merkle_root(leaves)
        proof = compute_inclusion_proof(leaves, 0)
        assert not verify_inclusion_proof(leaves[0], proof, "bad" * 16)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_inclusion_proof([], 0)

    def test_index_out_of_range(self) -> None:
        h = _sha256_hex("leaf")
        with pytest.raises(ValueError, match="out of range"):
            compute_inclusion_proof([h], 1)
        with pytest.raises(ValueError, match="out of range"):
            compute_inclusion_proof([h], -1)


class TestMerkleTree:
    """Tests for the MerkleTree dataclass."""

    def test_auto_computes_root(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(4)]
        tree = MerkleTree(leaves=leaves)
        assert tree.root == compute_merkle_root(leaves)

    def test_size(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(7)]
        tree = MerkleTree(leaves=leaves)
        assert tree.size == 7

    def test_inclusion_proof_and_verify(self) -> None:
        leaves = [_sha256_hex(f"leaf{i}") for i in range(4)]
        tree = MerkleTree(leaves=leaves)
        for i in range(4):
            proof = tree.inclusion_proof(i)
            assert tree.verify(leaves[i], proof)

    def test_empty_tree(self) -> None:
        tree = MerkleTree()
        assert tree.root == ""
        assert tree.size == 0
