"""Service layer for Merkle anchoring audit hash chains."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.crypto.anchoring import hash_for_timestamping, request_timestamp
from app.core.crypto.merkle import MerkleTree
from app.core.crypto.signing import sign_merkle_root
from app.db.models import AuditEvent, AuditMerkleRoot


class AuditAnchoringService:
    """Build and persist signed/timestamped Merkle roots for audit chains."""

    def __init__(self, session: AsyncSession, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def anchor_next_batch(self, *, tenant_id: UUID) -> AuditMerkleRoot | None:
        """Anchor the next unanchored batch for a tenant."""
        if not self._settings.audit_signing_key:
            raise ValueError("AUDIT_SIGNING_KEY is not configured")
        start_after = await self._last_anchored_sequence(tenant_id)
        events = await self._load_unanchored_events(
            tenant_id=tenant_id,
            start_after=start_after,
            limit=max(1, int(self._settings.audit_merkle_batch_size)),
        )
        if not events:
            return None

        hashes = [str(event.event_hash) for event in events if event.event_hash]
        if not hashes:
            return None
        sequences = [
            int(event.chain_sequence) for event in events if event.chain_sequence is not None
        ]
        tree = MerkleTree(leaves=hashes)

        signature = sign_merkle_root(tree.root, self._settings.audit_signing_key)
        signature_kid = self._settings.audit_signing_key_id
        signature_algorithm = "Ed25519"

        tsa_token: bytes | None = None
        timestamp_hash_algorithm: str | None = None
        if self._settings.tsa_url:
            tsa_token = await request_timestamp(
                hash_for_timestamping(tree.root),
                self._settings.tsa_url,
            )
            if tsa_token is not None:
                timestamp_hash_algorithm = "sha-256"

        anchor = AuditMerkleRoot(
            tenant_id=tenant_id,
            root_hash=tree.root,
            event_count=len(hashes),
            first_sequence=sequences[0],
            last_sequence=sequences[-1],
            signature=signature,
            signature_kid=signature_kid,
            signature_algorithm=signature_algorithm,
            tsa_token=tsa_token,
            timestamp_hash_algorithm=timestamp_hash_algorithm,
        )
        self._session.add(anchor)
        await self._session.flush()
        return anchor

    async def anchor_all_pending(
        self,
        *,
        tenant_id: UUID,
        max_batches: int | None = None,
    ) -> list[AuditMerkleRoot]:
        """Anchor all currently pending events for a tenant."""
        anchors: list[AuditMerkleRoot] = []
        batches = 0
        while True:
            if max_batches is not None and batches >= max_batches:
                break
            anchor = await self.anchor_next_batch(tenant_id=tenant_id)
            if anchor is None:
                break
            anchors.append(anchor)
            batches += 1
        return anchors

    async def _last_anchored_sequence(self, tenant_id: UUID) -> int:
        result = await self._session.execute(
            select(func.max(AuditMerkleRoot.last_sequence)).where(
                AuditMerkleRoot.tenant_id == tenant_id
            )
        )
        value = result.scalar_one_or_none()
        return int(value) if value is not None else -1

    async def _load_unanchored_events(
        self,
        *,
        tenant_id: UUID,
        start_after: int,
        limit: int,
    ) -> Sequence[AuditEvent]:
        result = await self._session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.chain_sequence.is_not(None),
                AuditEvent.event_hash.is_not(None),
                AuditEvent.chain_sequence > start_after,
            )
            .order_by(AuditEvent.chain_sequence.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
