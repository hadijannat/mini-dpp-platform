"""
QR Code generation service for DPP identification links.
"""

import io
from typing import Literal

import qrcode  # type: ignore[import-untyped]
from qrcode.image.styledpil import StyledPilImage  # type: ignore[import-untyped]
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

QRFormat = Literal["png", "svg"]


class QRCodeService:
    """
    Service for generating QR codes for DPP identification.

    Generates QR codes containing DPP viewer URLs following
    DPP4.0 "identification link on the product" pattern.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def generate_qr_code(
        self,
        dpp_url: str,
        format: QRFormat = "png",
        size: int = 400,
        with_logo: bool = False,
    ) -> bytes:
        """
        Generate a QR code for a DPP URL.

        Args:
            dpp_url: The URL to encode (DPP viewer endpoint)
            format: Output format (png or svg)
            size: Image size in pixels (for PNG)
            with_logo: Whether to embed a logo in center

        Returns:
            QR code image bytes
        """
        # Create QR code instance
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for logo
            box_size=10,
            border=4,
        )

        qr.add_data(dpp_url)
        qr.make(fit=True)

        if format == "png":
            return self._generate_png(qr, size, with_logo)
        else:
            return self._generate_svg(qr, size)

    def _generate_png(
        self,
        qr: qrcode.QRCode,
        size: int,
        _with_logo: bool,
    ) -> bytes:
        """Generate PNG QR code."""
        # Create styled image with rounded modules
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            fill_color="black",
            back_color="white",
        )

        # Resize to target size
        img = img.resize((size, size))

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)

        return buffer.read()

    def _generate_svg(self, qr: qrcode.QRCode, _size: int) -> bytes:
        """Generate SVG QR code."""
        import qrcode.image.svg  # type: ignore[import-untyped]

        factory = qrcode.image.svg.SvgImage
        img = qr.make_image(image_factory=factory)

        buffer = io.BytesIO()
        img.save(buffer)
        buffer.seek(0)

        return buffer.read()

    def build_dpp_url(self, dpp_id: str, short_link: bool = True) -> str:
        """
        Build the DPP viewer URL for QR code encoding.

        Args:
            dpp_id: The DPP identifier
            short_link: Use short link format (/p/{slug}) vs full (/dpp/{id})

        Returns:
            Complete URL for DPP viewer
        """
        base_url = (
            self._settings.cors_origins[0]
            if self._settings.cors_origins
            else "http://localhost:5173"
        )

        if short_link:
            # Generate short slug (first 8 chars of ID)
            slug = dpp_id.replace("-", "")[:8]
            return f"{base_url}/p/{slug}"
        else:
            return f"{base_url}/dpp/{dpp_id}"
