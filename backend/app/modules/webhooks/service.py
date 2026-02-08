"""Webhook subscription management and event delivery."""

import asyncio
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import WebhookDeliveryLog, WebhookSubscription
from app.modules.webhooks.client import deliver_webhook

logger = get_logger(__name__)


class WebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_subscription(
        self,
        tenant_id: UUID,
        url: str,
        events: list[str],
        created_by: str,
    ) -> WebhookSubscription:
        secret = secrets.token_hex(32)
        sub = WebhookSubscription(
            tenant_id=tenant_id,
            url=url,
            events=events,
            secret=secret,
            active=True,
            created_by_subject=created_by,
        )
        self.db.add(sub)
        await self.db.flush()
        return sub

    async def list_subscriptions(self, tenant_id: UUID) -> list[WebhookSubscription]:
        result = await self.db.execute(
            select(WebhookSubscription)
            .where(WebhookSubscription.tenant_id == tenant_id)
            .order_by(WebhookSubscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_subscription(
        self, subscription_id: UUID, tenant_id: UUID
    ) -> WebhookSubscription | None:
        result = await self.db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.id == subscription_id,
                WebhookSubscription.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_subscription(self, subscription_id: UUID, tenant_id: UUID) -> bool:
        sub = await self.get_subscription(subscription_id, tenant_id)
        if not sub:
            return False
        await self.db.delete(sub)
        await self.db.flush()
        return True

    async def get_deliveries(
        self, subscription_id: UUID, tenant_id: UUID, limit: int = 50
    ) -> list[WebhookDeliveryLog]:
        # Verify subscription belongs to tenant
        sub = await self.get_subscription(subscription_id, tenant_id)
        if not sub:
            return []
        result = await self.db.execute(
            select(WebhookDeliveryLog)
            .where(WebhookDeliveryLog.subscription_id == subscription_id)
            .order_by(WebhookDeliveryLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _find_matching_subscriptions(
        self, tenant_id: UUID, event_type: str
    ) -> list[WebhookSubscription]:
        """Find all active subscriptions matching the event type."""
        result = await self.db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.tenant_id == tenant_id,
                WebhookSubscription.active.is_(True),
            )
        )
        subs = result.scalars().all()
        # Filter by event type (events is a JSONB array)
        return [s for s in subs if event_type in s.events]

    async def _deliver_with_retries(
        self,
        sub: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Deliver webhook with exponential backoff retries."""
        settings = get_settings()
        max_retries = settings.webhook_max_retries

        for attempt in range(1, max_retries + 1):
            http_status, response_body, error = await deliver_webhook(
                url=sub.url,
                payload=payload,
                secret=sub.secret,
            )

            success = http_status is not None and 200 <= http_status < 300

            log = WebhookDeliveryLog(
                subscription_id=sub.id,
                event_type=event_type,
                payload=payload,
                http_status=http_status,
                response_body=response_body,
                attempt=attempt,
                success=success,
                error_message=error,
            )
            self.db.add(log)
            await self.db.flush()

            if success:
                logger.info(
                    "webhook_delivered",
                    subscription_id=str(sub.id),
                    event_type=event_type,
                    attempt=attempt,
                )
                return

            if attempt < max_retries:
                backoff = 4 ** (attempt - 1)  # 1s, 4s, 16s
                await asyncio.sleep(backoff)

        logger.warning(
            "webhook_delivery_exhausted",
            subscription_id=str(sub.id),
            event_type=event_type,
            max_retries=max_retries,
        )


async def trigger_webhooks(
    db: AsyncSession,
    tenant_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """
    Fire-and-forget webhook delivery for an event.

    Finds all matching subscriptions and delivers in parallel.
    Non-blocking — failures are logged, not raised.
    """
    settings = get_settings()
    if not settings.webhook_enabled:
        return

    service = WebhookService(db)
    subs = await service._find_matching_subscriptions(tenant_id, event_type)
    if not subs:
        return

    for sub in subs:
        # Use create_task for non-blocking delivery
        asyncio.create_task(
            service._deliver_with_retries(sub, event_type, payload)
        )
