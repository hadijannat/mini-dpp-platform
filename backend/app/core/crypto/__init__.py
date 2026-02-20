"""
Cryptographic audit trail primitives.

Pure library modules for tamper-evident integrity:
- **hash_chain**: SHA-256 hash chaining for sequential event integrity
- **merkle**: Merkle tree construction and inclusion proof verification
- **signing**: Ed25519 digital signatures for Merkle roots
- **anchoring**: RFC 3161 Timestamp Authority client
- **verification**: Chain and event verification utilities
"""

from app.core.crypto.canonicalization import (
    CANONICALIZATION_LEGACY_JSON_V1,
    CANONICALIZATION_RFC8785,
    SHA256_ALGORITHM,
    canonicalize_jcs_bytes,
    canonicalize_legacy_json_v1_bytes,
    sha256_hex_jcs,
)
from app.core.crypto.hash_chain import canonical_json, compute_event_hash
from app.core.crypto.merkle import (
    MerkleTree,
    compute_inclusion_proof,
    compute_merkle_root,
    verify_inclusion_proof,
)
from app.core.crypto.signing import (
    generate_signing_keypair,
    sign_merkle_root,
    verify_signature,
)
from app.core.crypto.verification import (
    ChainVerificationResult,
    verify_event,
    verify_hash_chain,
)

__all__ = [
    "canonical_json",
    "compute_event_hash",
    "canonicalize_jcs_bytes",
    "canonicalize_legacy_json_v1_bytes",
    "sha256_hex_jcs",
    "CANONICALIZATION_RFC8785",
    "CANONICALIZATION_LEGACY_JSON_V1",
    "SHA256_ALGORITHM",
    "MerkleTree",
    "compute_merkle_root",
    "compute_inclusion_proof",
    "verify_inclusion_proof",
    "sign_merkle_root",
    "verify_signature",
    "generate_signing_keypair",
    "ChainVerificationResult",
    "verify_event",
    "verify_hash_chain",
]
