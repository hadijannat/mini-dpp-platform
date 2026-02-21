"""DataMatrix renderer with optional runtime dependency."""

from __future__ import annotations

import io

from PIL import Image


class DataMatrixRenderer:
    """Render DataMatrix payloads when pylibdmtx/libdmtx is available."""

    @staticmethod
    def is_available() -> bool:
        try:
            from pylibdmtx.pylibdmtx import encode  # type: ignore[import-not-found]
        except Exception:
            return False
        return encode is not None

    def validate_payload(self, payload: str, _profile: dict[str, object]) -> None:
        if not payload.strip():
            raise ValueError("DataMatrix payload cannot be empty")
        if len(payload.encode("utf-8")) > 2000:
            raise ValueError("DataMatrix payload is too large for configured profile")

    def render(
        self,
        *,
        payload: str,
        output_type: str,
        profile: dict[str, object],
    ) -> bytes:
        self.validate_payload(payload, profile)

        if output_type != "png":
            raise ValueError("DataMatrix currently supports png output only")

        try:
            from pylibdmtx.pylibdmtx import encode
        except Exception as exc:
            raise NotImplementedError(
                "DataMatrix rendering unavailable. Install pylibdmtx and libdmtx runtime dependencies."
            ) from exc

        encoded = encode(payload.encode("utf-8"))
        image = Image.frombytes("RGB", (encoded.width, encoded.height), encoded.pixels)
        target_size = self._profile_int(profile, "size", encoded.width)
        if target_size > 0 and target_size != encoded.width:
            image = image.resize((target_size, target_size))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def _profile_int(profile: dict[str, object], key: str, default: int) -> int:
        raw = profile.get(key, default)
        try:
            return int(str(raw))
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer") from exc
