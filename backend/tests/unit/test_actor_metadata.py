"""Unit tests for actor metadata helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.security.actor_metadata import actor_payload, mask_email


def test_mask_email_masks_local_part() -> None:
    """Email masking should preserve domain and avoid exposing full local part."""
    assert mask_email("alice@example.com") == "a***e@example.com"
    assert mask_email("ab@example.com") == "a*@example.com"
    assert mask_email("a@example.com") == "*@example.com"


def test_actor_payload_prefers_user_record_and_masks_email() -> None:
    """Actor payload should return display name and masked email when available."""
    users_by_subject = {
        "subject-1": SimpleNamespace(
            display_name="Alice Doe",
            email="alice@example.com",
        ),
    }

    payload = actor_payload("subject-1", users_by_subject)

    assert payload == {
        "subject": "subject-1",
        "display_name": "Alice Doe",
        "email_masked": "a***e@example.com",
    }


def test_actor_payload_falls_back_to_subject_when_user_missing() -> None:
    """Actor payload should degrade safely when no profile exists."""
    payload = actor_payload("subject-missing", {})

    assert payload == {
        "subject": "subject-missing",
        "display_name": None,
        "email_masked": None,
    }
