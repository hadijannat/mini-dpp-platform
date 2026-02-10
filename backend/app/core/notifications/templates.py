"""Email templates for onboarding and role-request workflows."""

from dataclasses import dataclass


@dataclass(slots=True)
class EmailTemplate:
    """Rendered email payload."""

    subject: str
    text_body: str
    html_body: str | None = None


def build_role_request_submitted_requester_email(
    *,
    tenant_slug: str,
    requested_role: str,
    reason: str | None,
) -> EmailTemplate:
    reason_text = reason.strip() if reason else "No reason provided."
    subject = f"Role request received: {requested_role}"
    text = (
        f"Your request for '{requested_role}' access in tenant '{tenant_slug}' was received.\n\n"
        f"Reason: {reason_text}\n\n"
        "An administrator will review your request."
    )
    return EmailTemplate(subject=subject, text_body=text)


def build_role_request_submitted_admin_email(
    *,
    tenant_slug: str,
    requested_role: str,
    requester_subject: str,
    reason: str | None,
) -> EmailTemplate:
    reason_text = reason.strip() if reason else "No reason provided."
    subject = f"New role request: {requested_role} ({tenant_slug})"
    text = (
        f"A user submitted a new role request in tenant '{tenant_slug}'.\n\n"
        f"Requester subject: {requester_subject}\n"
        f"Requested role: {requested_role}\n"
        f"Reason: {reason_text}\n\n"
        "Please review the request in the DPP admin console."
    )
    return EmailTemplate(subject=subject, text_body=text)


def build_role_request_decision_email(
    *,
    tenant_slug: str,
    requested_role: str,
    approved: bool,
    review_note: str | None,
) -> EmailTemplate:
    status_text = "approved" if approved else "denied"
    review_note_text = review_note.strip() if review_note else "No review note provided."
    subject = f"Role request {status_text}: {requested_role}"
    text = (
        f"Your role request for '{requested_role}' in tenant '{tenant_slug}' was {status_text}.\n\n"
        f"Review note: {review_note_text}\n\n"
        "Sign in to DPP Platform to continue."
    )
    return EmailTemplate(subject=subject, text_body=text)
