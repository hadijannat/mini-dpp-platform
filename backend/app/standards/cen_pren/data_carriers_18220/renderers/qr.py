"""QR renderer honoring profile-driven error correction and quiet zones."""

from __future__ import annotations

from app.modules.qr.service import QRCodeService


class QRRenderer:
    """Render QR payloads using configurable profile attributes."""

    def __init__(self) -> None:
        self._qr = QRCodeService()

    def validate_payload(self, payload: str, profile: dict[str, object]) -> None:
        if not payload.strip():
            raise ValueError("QR payload cannot be empty")
        error_correction = str(profile.get("error_correction", "H")).upper()
        if error_correction not in {"L", "M", "Q", "H"}:
            raise ValueError("error_correction must be one of L, M, Q, H")
        quiet_zone_modules = self._profile_int(profile, "quiet_zone_modules", 4)
        if quiet_zone_modules < 1 or quiet_zone_modules > 16:
            raise ValueError("quiet_zone_modules must be between 1 and 16")

    def render(
        self,
        *,
        payload: str,
        output_type: str,
        profile: dict[str, object],
    ) -> bytes:
        self.validate_payload(payload, profile)
        return self._qr.generate_qr_code(
            dpp_url=payload,
            format=output_type,  # type: ignore[arg-type]
            size=self._profile_int(profile, "size", 400),
            foreground_color=str(profile.get("foreground_color", "#000000")),
            background_color=str(profile.get("background_color", "#FFFFFF")),
            include_text=bool(profile.get("include_text", True)),
            text_label=(
                str(profile["text_label"]) if profile.get("text_label") is not None else None
            ),
            error_correction=str(profile.get("error_correction", "H")).upper(),
            quiet_zone_modules=self._profile_int(profile, "quiet_zone_modules", 4),
        )

    @staticmethod
    def _profile_int(profile: dict[str, object], key: str, default: int) -> int:
        raw = profile.get(key, default)
        try:
            return int(str(raw))
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer") from exc
