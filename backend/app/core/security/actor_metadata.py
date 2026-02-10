"""Utilities for resolving and rendering actor identity metadata."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


def mask_email(email: str | None) -> str | None:
    """Mask an email address for UI-safe display."""
    if not email or "@" not in email:
        return None
    local_part, domain = email.split("@", 1)
    if not local_part:
        return None
    if len(local_part) == 1:
        masked_local = "*"
    elif len(local_part) == 2:
        masked_local = f"{local_part[0]}*"
    else:
        masked_local = f"{local_part[0]}{'*' * (len(local_part) - 2)}{local_part[-1]}"
    return f"{masked_local}@{domain}"


async def load_users_by_subject(
    db: AsyncSession,
    subjects: Iterable[str],
) -> dict[str, User]:
    """Load user rows keyed by OIDC subject."""
    unique_subjects = sorted({subject for subject in subjects if subject})
    if not unique_subjects:
        return {}

    result = await db.execute(select(User).where(User.subject.in_(unique_subjects)))
    users = result.scalars().all()
    return {user.subject: user for user in users}


def actor_payload(subject: str, users_by_subject: dict[str, User]) -> dict[str, str | None]:
    """Build an actor payload with display metadata."""
    user = users_by_subject.get(subject)
    return {
        "subject": subject,
        "display_name": user.display_name if user else None,
        "email_masked": mask_email(user.email if user else None),
    }
