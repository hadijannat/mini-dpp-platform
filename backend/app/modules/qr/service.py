"""
QR Code and Data Carrier generation service for DPP identification links.

Supports:
- Standard QR codes with DPP viewer URLs
- GS1 Digital Link format per EU DPP requirements
- Customizable colors and branding
- Multiple output formats (PNG, SVG, PDF)
"""

import io
from typing import Literal

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]
from qrcode.image.styledpil import StyledPilImage  # type: ignore[import-untyped]
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

QRFormat = Literal["png", "svg", "pdf"]


class QRCodeService:
    """
    Service for generating QR codes and data carriers for DPP identification.

    Generates QR codes containing DPP viewer URLs following
    DPP4.0 "identification link on the product" pattern, with optional
    GS1 Digital Link format for EU ESPR compliance.
    """

    # Default GS1 resolver URL
    DEFAULT_GS1_RESOLVER = "https://id.gs1.org"

    def __init__(self) -> None:
        self._settings = get_settings()

    def generate_qr_code(
        self,
        dpp_url: str,
        format: QRFormat = "png",
        size: int = 400,
        with_logo: bool = False,
        foreground_color: str = "#000000",
        background_color: str = "#FFFFFF",
        include_text: bool = False,
        text_label: str | None = None,
    ) -> bytes:
        """
        Generate a QR code for a DPP URL.

        Args:
            dpp_url: The URL to encode (DPP viewer endpoint)
            format: Output format (png, svg, or pdf)
            size: Image size in pixels (for PNG)
            with_logo: Whether to embed a logo in center
            foreground_color: QR code foreground color (hex)
            background_color: QR code background color (hex)
            include_text: Whether to add text label below QR
            text_label: Custom text to display below QR code

        Returns:
            QR code image bytes
        """
        # Parse colors
        fg_color = self._hex_to_rgb(foreground_color)
        bg_color = self._hex_to_rgb(background_color)

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
            return self._generate_png(
                qr, size, with_logo, fg_color, bg_color, include_text, text_label
            )
        elif format == "pdf":
            return self._generate_pdf(
                qr, size, fg_color, bg_color, include_text, text_label
            )
        else:
            return self._generate_svg(qr, size)

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    def _generate_png(
        self,
        qr: qrcode.QRCode,
        size: int,
        _with_logo: bool,
        fg_color: tuple[int, int, int],
        bg_color: tuple[int, int, int],
        include_text: bool,
        text_label: str | None,
    ) -> bytes:
        """Generate PNG QR code with optional text label."""
        # Create styled image with rounded modules
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            fill_color=fg_color,
            back_color=bg_color,
        )

        # Resize to target size
        img = img.resize((size, size))

        # Add text label if requested
        if include_text and text_label:
            img = self._add_text_label(img, text_label, size, fg_color, bg_color)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)

        return buffer.read()

    def _add_text_label(
        self,
        img: Image.Image,
        text: str,
        size: int,
        fg_color: tuple[int, int, int],
        bg_color: tuple[int, int, int],
    ) -> Image.Image:
        """Add text label below QR code."""
        # Calculate text area height
        text_height = int(size * 0.12)
        total_height = size + text_height

        # Create new image with space for text
        new_img = Image.new("RGB", (size, total_height), bg_color)
        new_img.paste(img, (0, 0))

        # Draw text
        draw = ImageDraw.Draw(new_img)

        # Try to use a system font, fall back to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(size * 0.05))
        except OSError:
            font = ImageFont.load_default()

        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (size - text_width) // 2
        y = size + (text_height - (bbox[3] - bbox[1])) // 2

        draw.text((x, y), text, fill=fg_color, font=font)

        return new_img

    def _generate_svg(self, qr: qrcode.QRCode, _size: int) -> bytes:
        """Generate SVG QR code."""
        import qrcode.image.svg  # type: ignore[import-untyped]

        factory = qrcode.image.svg.SvgImage
        img = qr.make_image(image_factory=factory)

        buffer = io.BytesIO()
        img.save(buffer)
        buffer.seek(0)

        return buffer.read()

    def _generate_pdf(
        self,
        qr: qrcode.QRCode,
        size: int,
        fg_color: tuple[int, int, int],
        bg_color: tuple[int, int, int],
        include_text: bool,
        text_label: str | None,
    ) -> bytes:
        """Generate PDF with QR code for print-ready output."""
        # First generate PNG
        png_bytes = self._generate_png(
            qr, size, False, fg_color, bg_color, include_text, text_label
        )

        # Convert PNG to PDF using PIL
        img = Image.open(io.BytesIO(png_bytes))
        pdf_buffer = io.BytesIO()
        img.save(pdf_buffer, format="PDF", resolution=300)
        pdf_buffer.seek(0)

        return pdf_buffer.read()

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

    def build_gs1_digital_link(
        self,
        gtin: str,
        serial: str,
        resolver_url: str | None = None,
    ) -> str:
        """
        Build GS1 Digital Link URL per EU DPP/ESPR requirements.

        The GS1 Digital Link format provides a standardized way to
        encode product identifiers in QR codes, enabling lookup
        against the global GS1 resolver network.

        Args:
            gtin: Global Trade Item Number (14 digits recommended)
            serial: Serial number for the specific product instance
            resolver_url: Custom GS1 resolver URL (default: id.gs1.org)

        Returns:
            GS1 Digital Link URL
        """
        base_url = resolver_url or getattr(
            self._settings, "gs1_resolver_url", self.DEFAULT_GS1_RESOLVER
        )

        # Clean GTIN (remove any non-digits)
        clean_gtin = "".join(filter(str.isdigit, gtin))

        # Pad GTIN to 14 digits if needed
        if len(clean_gtin) < 14:
            clean_gtin = clean_gtin.zfill(14)

        # Build GS1 Digital Link
        # Format: https://id.gs1.org/01/{GTIN}/21/{serial}
        return f"{base_url}/01/{clean_gtin}/21/{serial}"

    def extract_gtin_from_asset_ids(self, asset_ids: dict) -> tuple[str, str]:
        """
        Extract GTIN and serial from DPP asset identifiers.

        Falls back to generating a pseudo-GTIN from the manufacturer part ID
        if no real GTIN is available.

        Args:
            asset_ids: Dictionary with manufacturerPartId and serialNumber

        Returns:
            Tuple of (gtin, serial)
        """
        manufacturer_part_id = asset_ids.get("manufacturerPartId", "")
        serial = asset_ids.get("serialNumber", "")

        # Check for explicit GTIN in asset_ids
        gtin = asset_ids.get("globalAssetId", "")
        if not gtin:
            gtin = asset_ids.get("gtin", "")

        # If no GTIN, create a pseudo-GTIN from part ID
        if not gtin:
            # Generate a 13-digit hash-based identifier
            import hashlib

            hash_input = manufacturer_part_id.encode()
            hash_digest = hashlib.sha256(hash_input).hexdigest()
            # Take first 13 digits and add check digit position
            gtin = hash_digest[:12].upper()
            # Ensure it's numeric (convert hex to decimal representation)
            gtin = str(int(gtin, 16) % 10**13).zfill(13)

        return gtin, serial
