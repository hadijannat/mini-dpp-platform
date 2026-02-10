"""SMTP email client used for best-effort workflow notifications."""

from __future__ import annotations

import asyncio
import smtplib
from collections.abc import Iterable
from email.message import EmailMessage

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailClient:
    """Small SMTP wrapper for transactional notification emails."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def send_email(
        self,
        recipients: Iterable[str],
        *,
        subject: str,
        text_body: str,
        html_body: str | None = None,
    ) -> bool:
        """Send an email asynchronously. Returns True on success."""
        recipient_list = self._normalize_recipients(recipients)
        if not recipient_list:
            logger.warning("notification_email_no_recipients", subject=subject)
            return False

        if not self._settings.notifications_email_enabled:
            logger.info(
                "notification_email_disabled",
                subject=subject,
                recipients=len(recipient_list),
            )
            return False

        if (
            not self._settings.notifications_smtp_host
            or not self._settings.notifications_from_email
        ):
            logger.warning(
                "notification_email_config_incomplete",
                smtp_host=bool(self._settings.notifications_smtp_host),
                from_email=bool(self._settings.notifications_from_email),
            )
            return False

        return await asyncio.to_thread(
            self._send_sync,
            recipient_list,
            subject,
            text_body,
            html_body,
        )

    def _send_sync(
        self,
        recipients: list[str],
        subject: str,
        text_body: str,
        html_body: str | None,
    ) -> bool:
        msg = EmailMessage()
        from_display = self._settings.notifications_from_name.strip()
        from_email = self._settings.notifications_from_email.strip()
        msg["Subject"] = subject
        msg["From"] = f"{from_display} <{from_email}>" if from_display else from_email
        msg["To"] = ", ".join(recipients)
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        try:
            with smtplib.SMTP(
                host=self._settings.notifications_smtp_host,
                port=self._settings.notifications_smtp_port,
                timeout=10,
            ) as smtp:
                if self._settings.notifications_smtp_starttls:
                    smtp.starttls()
                username = (self._settings.notifications_smtp_user or "").strip()
                password = (self._settings.notifications_smtp_password or "").strip()
                if username:
                    smtp.login(username, password)
                smtp.send_message(msg)
            logger.info(
                "notification_email_sent",
                subject=subject,
                recipients=len(recipients),
            )
            return True
        except Exception:
            logger.exception(
                "notification_email_send_failed",
                subject=subject,
                recipients=recipients,
            )
            return False

    @staticmethod
    def _normalize_recipients(recipients: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for recipient in recipients:
            email = recipient.strip()
            if not email:
                continue
            lowered = email.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(email)
        return normalized
