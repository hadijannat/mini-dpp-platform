"""
QR Code and Data Carrier generation service for DPP identification links.

Supports:
- Standard QR codes with DPP viewer URLs
- GS1 Digital Link format per EU DPP requirements
- Customizable colors and branding
- Multiple output formats (PNG, SVG, PDF)
"""

import hashlib
import io
from typing import Literal
from urllib.parse import quote

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont
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
            return self._generate_png(qr, size, fg_color, bg_color, include_text, text_label)
        elif format == "pdf":
            return self._generate_pdf(qr, size, fg_color, bg_color, include_text, text_label)
        else:
            return self._generate_svg(qr, size)

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color string (e.g., "#FF0000" or "FF0000")

        Returns:
            RGB tuple (r, g, b) with values 0-255

        Raises:
            ValueError: If hex_color is not a valid 6-character hex string
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            raise ValueError(f"Invalid hex color: must be 6 characters, got {len(hex_color)}")
        try:
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore
        except ValueError as e:
            raise ValueError(f"Invalid hex color: {hex_color}") from e

    def _generate_png(
        self,
        qr: qrcode.QRCode,
        size: int,
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
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(size * 0.05)
            )
        except OSError:
            font = ImageFont.load_default()  # type: ignore[assignment]

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
        png_bytes = self._generate_png(qr, size, fg_color, bg_color, include_text, text_label)

        # Convert PNG to PDF using PIL
        img = Image.open(io.BytesIO(png_bytes))
        pdf_buffer = io.BytesIO()
        img.save(pdf_buffer, format="PDF", resolution=300)
        pdf_buffer.seek(0)

        return pdf_buffer.read()

    def build_iec61406_link(self, asset_ids: dict[str, str], base_url: str) -> str:
        """Build an IEC 61406 identification link URL.

        Encodes ``manufacturerPartId`` and ``serialNumber`` as query
        parameters on the given *base_url*.

        Args:
            asset_ids: DPP asset identifiers dict.
            base_url: Base URL of the DPP resource.

        Returns:
            IEC 61406 identification link URL.
        """
        manufacturer = asset_ids.get("manufacturerPartId", "")
        serial = asset_ids.get("serialNumber", "")
        return f"{base_url.rstrip('/')}?mid={quote(manufacturer)}&sn={quote(serial)}"

    def build_dpp_url(
        self,
        dpp_id: str,
        tenant_slug: str | None = None,
        short_link: bool = True,
    ) -> str:
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
            if tenant_slug:
                return f"{base_url}/t/{tenant_slug}/p/{slug}"
            return f"{base_url}/p/{slug}"
        if tenant_slug:
            return f"{base_url}/t/{tenant_slug}/dpp/{dpp_id}"
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
        base_url = str(
            resolver_url
            or getattr(self._settings, "gs1_resolver_url", None)
            or self.DEFAULT_GS1_RESOLVER
        )
        base_url = base_url.rstrip("/")

        # Clean GTIN (remove any non-digits)
        clean_gtin = "".join(filter(str.isdigit, gtin))
        if not clean_gtin:
            raise ValueError("GTIN is required for GS1 Digital Link")
        serial_value = str(serial).strip()
        if not serial_value:
            raise ValueError("Serial number is required for GS1 Digital Link")

        # Pad GTIN to 14 digits if needed
        if len(clean_gtin) < 14:
            clean_gtin = clean_gtin.zfill(14)

        # Validate check digit per GS1 General Specifications Section 7.9
        if not self.validate_gtin(clean_gtin):
            expected = self._compute_gtin_check_digit(clean_gtin[:-1])
            raise ValueError(
                f"GTIN {clean_gtin} has an invalid check digit. Expected check digit: {expected}"
            )

        encoded_gtin = quote(clean_gtin, safe="")
        encoded_serial = quote(serial_value, safe="")

        # Build GS1 Digital Link
        # Format: https://id.gs1.org/01/{GTIN}/21/{serial}
        return f"{base_url}/01/{encoded_gtin}/21/{encoded_serial}"

    def extract_gtin_from_asset_ids(self, asset_ids: dict[str, str]) -> tuple[str, str, bool]:
        """
        Extract GTIN and serial from DPP asset identifiers.

        Falls back to generating a pseudo-GTIN from the manufacturer part ID
        if no real GTIN is available.

        Args:
            asset_ids: Dictionary with manufacturerPartId and serialNumber

        Returns:
            Tuple of (gtin, serial, is_pseudo_gtin)
        """
        manufacturer_part_id = asset_ids.get("manufacturerPartId", "")
        serial = asset_ids.get("serialNumber", "")

        # Check for explicit GTIN in asset_ids
        gtin = asset_ids.get("gtin", "")
        if not gtin:
            candidate = asset_ids.get("globalAssetId", "")
            if isinstance(candidate, str) and candidate.isdigit():
                gtin = candidate

        # If no GTIN, create a pseudo-GTIN from part ID with valid check digit
        if not gtin:
            hash_input = manufacturer_part_id.encode()
            hash_digest = hashlib.sha256(hash_input).hexdigest()
            # Generate 13 digits from hash, then append valid check digit for GTIN-14
            digits_13 = str(int(hash_digest[:12], 16) % 10**13).zfill(13)
            check_digit = self._compute_gtin_check_digit(digits_13)
            gtin = digits_13 + check_digit
            return gtin, serial, True

        return gtin, serial, False

    @staticmethod
    def _compute_gtin_check_digit(digits: str) -> str:
        """
        Compute GS1 check digit using mod-10 weight-3 algorithm.

        Per GS1 General Specifications Section 7.9: starting from the
        rightmost digit, alternate weights of 3 and 1 are applied.
        The check digit makes the total sum a multiple of 10.

        Args:
            digits: The GTIN digits WITHOUT the check digit (7, 11, 12, or 13 digits)

        Returns:
            Single character check digit ('0'-'9')
        """
        total = 0
        for i, ch in enumerate(reversed(digits)):
            weight = 3 if i % 2 == 0 else 1
            total += int(ch) * weight
        return str((10 - (total % 10)) % 10)

    @staticmethod
    def validate_gtin(gtin: str) -> bool:
        """
        Validate a GTIN check digit.

        Supports GTIN-8, GTIN-12, GTIN-13, and GTIN-14 formats.

        Args:
            gtin: Complete GTIN string (digits only)

        Returns:
            True if the check digit is valid
        """
        clean = "".join(filter(str.isdigit, gtin))
        if len(clean) not in (8, 12, 13, 14):
            return False
        payload = clean[:-1]
        expected = QRCodeService._compute_gtin_check_digit(payload)
        return clean[-1] == expected
