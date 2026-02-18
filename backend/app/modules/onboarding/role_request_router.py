"""
Role upgrade request API endpoints.

Mounted under: {tenant_prefix}/role-requests
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.tenancy import TenantAdmin, TenantMemberDep
from app.db.models import RoleRequestStatus
from app.db.session import DbSession
from app.modules.onboarding.role_request_service import RoleRequestService
from app.modules.onboarding.schemas import (
    RoleRequestCreate,
    RoleRequestResponse,
    RoleRequestReview,
)

router = APIRouter()


def _to_response(
    req: object,
    *,
    requester_email: str | None = None,
    requester_display_name: str | None = None,
) -> RoleRequestResponse:
    """Convert a RoleUpgradeRequest ORM instance to a response schema."""
    from app.db.models import RoleUpgradeRequest

    assert isinstance(req, RoleUpgradeRequest)
    return RoleRequestResponse(
        id=req.id,
        user_subject=req.user_subject,
        requested_role=req.requested_role.value,
        status=req.status.value,
        reason=req.reason,
        reviewed_by=req.reviewed_by,
        review_note=req.review_note,
        reviewed_at=req.reviewed_at.isoformat() if req.reviewed_at else None,
        created_at=req.created_at.isoformat(),
        requester_email=requester_email,
        requester_display_name=requester_display_name,
    )


async def _to_response_with_identity(
    req: object,
    svc: RoleRequestService,
) -> RoleRequestResponse:
    from app.db.models import RoleUpgradeRequest

    assert isinstance(req, RoleUpgradeRequest)
    identity_map = await svc.get_requester_identity_map([req.user_subject])
    requester_email, requester_display_name = identity_map.get(req.user_subject, (None, None))
    return _to_response(
        req,
        requester_email=requester_email,
        requester_display_name=requester_display_name,
    )


async def _to_responses_with_identity(
    requests: list[object],
    svc: RoleRequestService,
) -> list[RoleRequestResponse]:
    from app.db.models import RoleUpgradeRequest

    valid_requests = [req for req in requests if isinstance(req, RoleUpgradeRequest)]
    identity_map = await svc.get_requester_identity_map(req.user_subject for req in valid_requests)
    return [
        _to_response(
            req,
            requester_email=identity_map.get(req.user_subject, (None, None))[0],
            requester_display_name=identity_map.get(req.user_subject, (None, None))[1],
        )
        for req in valid_requests
    ]


@router.post("", response_model=RoleRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_role_request(
    body: RoleRequestCreate,
    db: DbSession,
    context: TenantMemberDep,
) -> RoleRequestResponse:
    """Submit a role upgrade request (any tenant member)."""
    svc = RoleRequestService(db)
    try:
        req = await svc.create_request(
            tenant_id=context.tenant_id,
            user=context.user,
            requested_role=body.requested_role,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return await _to_response_with_identity(req, svc)


@router.get("/mine", response_model=list[RoleRequestResponse])
async def list_my_requests(
    db: DbSession,
    context: TenantMemberDep,
) -> list[RoleRequestResponse]:
    """List the current user's role requests."""
    svc = RoleRequestService(db)
    requests = await svc.get_user_requests(context.tenant_id, context.user.sub)
    return await _to_responses_with_identity(list(requests), svc)


@router.get("", response_model=list[RoleRequestResponse])
async def list_all_requests(
    db: DbSession,
    context: TenantAdmin,
    status_filter: str | None = None,
) -> list[RoleRequestResponse]:
    """List all role requests (admin only). Optional ?status_filter=pending."""
    parsed_filter: RoleRequestStatus | None = None
    if status_filter:
        try:
            parsed_filter = RoleRequestStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}",
            )
    svc = RoleRequestService(db)
    requests = await svc.list_requests(context.tenant_id, parsed_filter)
    return await _to_responses_with_identity(list(requests), svc)


@router.patch("/{request_id}", response_model=RoleRequestResponse)
async def review_role_request(
    request_id: UUID,
    body: RoleRequestReview,
    db: DbSession,
    context: TenantAdmin,
) -> RoleRequestResponse:
    """Approve or deny a role request (admin only)."""
    svc = RoleRequestService(db)
    try:
        req = await svc.review_request(
            request_id=request_id,
            tenant_id=context.tenant_id,
            approved=body.approved,
            reviewer=context.user,
            review_note=body.review_note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return await _to_response_with_identity(req, svc)
