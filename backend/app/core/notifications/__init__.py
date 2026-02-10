"""Notification utilities for onboarding and role-request workflows."""

from app.core.notifications.email_client import EmailClient
from app.core.notifications.templates import (
    EmailTemplate,
    build_role_request_decision_email,
    build_role_request_submitted_admin_email,
    build_role_request_submitted_requester_email,
)

__all__ = [
    "EmailClient",
    "EmailTemplate",
    "build_role_request_decision_email",
    "build_role_request_submitted_admin_email",
    "build_role_request_submitted_requester_email",
]
