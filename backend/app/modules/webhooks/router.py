"""API Router for webhook subscription management."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.tenancy import TenantAdmin, TenantContextDep
from app.db.session import DbSession
from app.modules.webhooks.schemas import (
    DeliveryLogResponse,
    WebhookCreate,
    WebhookResponse,
)
from app.modules.webhooks.service import WebhookService, trigger_webhooks

router = APIRouter()


def _sub_to_response(sub: object) -> WebhookResponse:
    """Convert ORM model to response schema."""
    from app.db.models import WebhookSubscription

    assert isinstance(sub, WebhookSubscription)
    return WebhookResponse(
        id=sub.id,
        url=sub.url,
        events=sub.events,
        active=sub.active,
        created_by_subject=sub.created_by_subject,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    db: DbSession,
    tenant: TenantAdmin,
) -> list[WebhookResponse]:
    """List all webhook subscriptions for the tenant."""
    service = WebhookService(db)
    subs = await service.list_subscriptions(tenant.tenant_id)
    return [_sub_to_response(s) for s in subs]


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    db: DbSession,
    tenant: TenantAdmin,
) -> WebhookResponse:
    """Create a new webhook subscription."""
    service = WebhookService(db)
    sub = await service.create_subscription(
        tenant_id=tenant.tenant_id,
        url=str(body.url),
        events=list(body.events),
        created_by=tenant.user.sub,
    )
    await db.commit()
    return _sub_to_response(sub)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: DbSession,
    tenant: TenantAdmin,
) -> None:
    """Delete a webhook subscription."""
    service = WebhookService(db)
    deleted = await service.delete_subscription(webhook_id, tenant.tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook subscription not found",
        )
    await db.commit()


@router.get("/{webhook_id}/deliveries", response_model=list[DeliveryLogResponse])
async def list_deliveries(
    webhook_id: UUID,
    db: DbSession,
    tenant: TenantAdmin,
) -> list[DeliveryLogResponse]:
    """List recent delivery attempts for a webhook subscription."""
    service = WebhookService(db)
    deliveries = await service.get_deliveries(webhook_id, tenant.tenant_id)
    return [
        DeliveryLogResponse(
            id=d.id,
            subscription_id=d.subscription_id,
            event_type=d.event_type,
            payload=d.payload,
            http_status=d.http_status,
            response_body=d.response_body,
            attempt=d.attempt,
            success=d.success,
            error_message=d.error_message,
            created_at=d.created_at,
        )
        for d in deliveries
    ]


@router.post("/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    webhook_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
) -> dict[str, str]:
    """Send a test payload to verify webhook connectivity."""
    service = WebhookService(db)
    sub = await service.get_subscription(webhook_id, tenant.tenant_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook subscription not found",
        )

    test_payload = {
        "event": "WEBHOOK_TEST",
        "tenant_id": str(tenant.tenant_id),
        "message": "This is a test webhook delivery from DPP Platform.",
    }

    await trigger_webhooks(db, tenant.tenant_id, "WEBHOOK_TEST", test_payload)
    return {"status": "Test delivery initiated"}
