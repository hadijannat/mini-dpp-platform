"""Pydantic schemas for the onboarding module."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OnboardingBlocker = Literal[
    "email_unverified",
    "tenant_missing",
    "tenant_inactive",
    "onboarding_disabled",
]
OnboardingNextAction = Literal[
    "provision",
    "resend_verification",
    "request_role_upgrade",
    "go_home",
]


class OnboardingStatusResponse(BaseModel):
    """Response for the onboarding status check."""

    provisioned: bool
    tenant_slug: str | None = None
    role: str | None = None
    email_verified: bool
    blockers: list[OnboardingBlocker] = Field(default_factory=list)
    next_actions: list[OnboardingNextAction] = Field(default_factory=list)


class ResendVerificationResponse(BaseModel):
    """Response for resend verification endpoint."""

    queued: bool
    cooldown_seconds: int
    next_allowed_at: str | None = None


class RoleRequestCreate(BaseModel):
    """Request body for submitting a role upgrade request."""

    requested_role: str = Field(..., description="Role to request (e.g. 'publisher')")
    reason: str | None = Field(None, max_length=1000, description="Optional reason for the request")


class RoleRequestReview(BaseModel):
    """Request body for approving/denying a role request."""

    approved: bool
    review_note: str | None = Field(
        None, max_length=1000, description="Optional note explaining the decision"
    )


class RoleRequestResponse(BaseModel):
    """Response for a role upgrade request."""

    id: UUID
    user_subject: str
    requested_role: str
    status: str
    reason: str | None = None
    reviewed_by: str | None = None
    review_note: str | None = None
    reviewed_at: str | None = None
    created_at: str
    requester_email: str | None = None
    requester_display_name: str | None = None

    model_config = {"from_attributes": True}
