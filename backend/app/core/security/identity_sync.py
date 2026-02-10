"""Identity synchronization utilities for authenticated requests."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.oidc import TokenPayload
from app.db.models import User, UserRole


def _derive_display_name(user: TokenPayload) -> str | None:
    preferred = user.preferred_username
    if preferred:
        return preferred

    raw_name = user.raw_claims.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()

    given_name = user.raw_claims.get("given_name")
    family_name = user.raw_claims.get("family_name")
    if isinstance(given_name, str) and isinstance(family_name, str):
        full_name = f"{given_name.strip()} {family_name.strip()}".strip()
        if full_name:
            return full_name

    return user.email


def _build_attrs(user: TokenPayload) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if user.org:
        attrs["org"] = user.org
    if user.bpn:
        attrs["bpn"] = user.bpn
    if user.clearance:
        attrs["clearance"] = user.clearance
    return attrs


async def sync_user_from_token(db: AsyncSession, user: TokenPayload) -> User:
    """Upsert the `users` row from current JWT claims."""
    result = await db.execute(select(User).where(User.subject == user.sub))
    existing = result.scalar_one_or_none()

    display_name = _derive_display_name(user)
    attrs = _build_attrs(user)

    if existing:
        if user.email and existing.email != user.email:
            existing.email = user.email
        if display_name and existing.display_name != display_name:
            existing.display_name = display_name
        if attrs:
            merged = dict(existing.attrs or {})
            if merged != {**merged, **attrs}:
                merged.update(attrs)
                existing.attrs = merged
        return existing

    created = User(
        subject=user.sub,
        email=user.email,
        display_name=display_name,
        role=UserRole.VIEWER,
        attrs=attrs,
    )
    db.add(created)
    await db.flush()
    return created
