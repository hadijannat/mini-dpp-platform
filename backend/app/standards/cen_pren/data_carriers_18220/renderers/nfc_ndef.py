"""NFC renderer producing NDEF URI records."""

from __future__ import annotations


class NFCRenderer:
    """Generate an NFC Forum NDEF URI record payload."""

    def validate_payload(self, payload: str, profile: dict[str, object]) -> None:
        if not payload.strip():
            raise ValueError("NFC payload cannot be empty")
        memory_bytes = self._profile_int(profile, "nfc_memory_bytes", 512)
        if memory_bytes < 16:
            raise ValueError("nfc_memory_bytes must be at least 16")
        estimated = len(payload.encode("utf-8")) + 5
        if estimated > memory_bytes:
            raise ValueError(
                f"NFC payload exceeds configured memory ({estimated} bytes > {memory_bytes})"
            )

    def render(
        self,
        *,
        payload: str,
        output_type: str,
        profile: dict[str, object],
    ) -> bytes:
        self.validate_payload(payload, profile)
        if output_type != "ndef":
            raise ValueError("NFC renderer requires output_type='ndef'")

        uri_bytes = payload.encode("utf-8")
        if len(uri_bytes) > 255:
            raise ValueError("NFC URI payload too large for short NDEF record")

        # NDEF short record, TNF=Well-known, type='U', no URI abbreviation prefix.
        header = bytes([0xD1, 0x01, len(uri_bytes) + 1, 0x55, 0x00])
        return header + uri_bytes

    @staticmethod
    def _profile_int(profile: dict[str, object], key: str, default: int) -> int:
        raw = profile.get(key, default)
        try:
            return int(str(raw))
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer") from exc
