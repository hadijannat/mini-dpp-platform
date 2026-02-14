"""CIRPASS source parsing helpers (official CIRPASS + Zenodo only)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader

from app.modules.cirpass.schemas import (
    CirpassLevelResponse,
    CirpassStoryResponse,
    ParsedCirpassFeed,
)

_ALLOWED_CIRPASS_HOSTS = {"cirpassproject.eu", "www.cirpassproject.eu"}
_ALLOWED_ZENODO_HOSTS = {"zenodo.org", "www.zenodo.org", "doi.org"}

_LEVEL_METADATA: dict[str, tuple[str, str]] = {
    "create": (
        "CREATE",
        "Build a complete DPP payload with mandatory sustainability fields.",
    ),
    "access": (
        "ACCESS",
        "Route role-based views so each actor receives only permitted information.",
    ),
    "update": (
        "UPDATE",
        "Append trusted lifecycle updates without breaking prior provenance links.",
    ),
    "transfer": (
        "TRANSFER",
        "Transfer custody/ownership while preserving confidentiality boundaries.",
    ),
    "deactivate": (
        "DEACTIVATE",
        "Close the lifecycle and surface recovered material insights for circularity.",
    ),
}

_LEVEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "create": (
        "create",
        "mint",
        "onboard",
        "register",
        "author",
        "initial",
        "material",
        "carbon",
        "passport",
    ),
    "access": (
        "access",
        "consumer",
        "authority",
        "surveillance",
        "visibility",
        "permission",
        "credential",
        "read",
    ),
    "update": (
        "update",
        "repair",
        "maintenance",
        "service",
        "event",
        "history",
        "replace",
    ),
    "transfer": (
        "transfer",
        "handover",
        "ownership",
        "supply chain",
        "logistics",
        "exchange",
        "partner",
    ),
    "deactivate": (
        "deactivate",
        "end-of-life",
        "recycle",
        "remanufacture",
        "waste",
        "recovery",
        "circular",
    ),
}

_FALLBACK_STORIES: dict[str, tuple[str, str]] = {
    "create": (
        "Initialize a compliant passport",
        "Responsible operators compose required DPP attributes before placing products on market.",
    ),
    "access": (
        "Control who sees what",
        "Consumers, authorities, and partners receive role-scoped views under policy constraints.",
    ),
    "update": (
        "Capture lifecycle changes",
        "Repair and maintenance operations append auditable events to the existing passport timeline.",
    ),
    "transfer": (
        "Move product context safely",
        "Ownership and responsibility data is transferred without exposing restricted business details.",
    ),
    "deactivate": (
        "Close and loop back",
        "End-of-life declarations preserve provenance while surfacing material recovery opportunities.",
    ),
}


class CirpassParseError(RuntimeError):
    """Raised when source extraction fails."""


class CirpassSourceParser:
    """Parser that extracts latest CIRPASS stories from official sources only."""

    def __init__(self, results_url: str) -> None:
        self.results_url = results_url
        self._assert_url_allowed(results_url, allow_zenodo=False)

    async def fetch_latest_feed(self, client: httpx.AsyncClient) -> ParsedCirpassFeed:
        results_html = await self._fetch_results_page(client)
        zenodo_record_url, zenodo_record_id = self._extract_zenodo_record_reference(results_html)
        zenodo_record = await self._fetch_zenodo_record(client, zenodo_record_id)

        pdf_url = self._select_pdf_url(zenodo_record)
        pdf_text = await self._download_pdf_text(client, pdf_url)

        version = self._extract_version(pdf_text, zenodo_record)
        release_date = self._extract_release_date(zenodo_record)
        level_map = self._extract_level_stories(pdf_text)

        levels = [
            CirpassLevelResponse(
                level=level,
                label=_LEVEL_METADATA[level][0],
                objective=_LEVEL_METADATA[level][1],
                stories=stories,
            )
            for level, stories in level_map.items()
        ]

        return ParsedCirpassFeed(
            version=version,
            release_date=release_date,
            source_url=self.results_url,
            zenodo_record_url=zenodo_record_url,
            zenodo_record_id=zenodo_record_id,
            levels=levels,
        )

    async def _fetch_results_page(self, client: httpx.AsyncClient) -> str:
        response = await client.get(self.results_url)
        response.raise_for_status()
        return response.text

    async def _fetch_zenodo_record(
        self,
        client: httpx.AsyncClient,
        record_id: str,
    ) -> dict[str, object]:
        api_url = f"https://zenodo.org/api/records/{record_id}"
        response = await client.get(api_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise CirpassParseError("Invalid Zenodo record response")
        return payload

    async def _download_pdf_text(self, client: httpx.AsyncClient, pdf_url: str) -> str:
        self._assert_url_allowed(pdf_url, allow_zenodo=True)
        response = await client.get(pdf_url)
        response.raise_for_status()

        reader = PdfReader(BytesIO(response.content))
        parts: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                parts.append(extracted)

        text = "\n".join(parts).strip()
        if not text:
            raise CirpassParseError("Unable to extract text from CIRPASS PDF")
        return text

    def _extract_zenodo_record_reference(self, html: str) -> tuple[str, str]:
        links: list[tuple[int, str, str]] = []

        for match in re.finditer(
            r"href=[\"'](?P<href>https?://[^\"']+)[\"'][^>]*>(?P<label>[^<]*)",
            html,
            flags=re.IGNORECASE,
        ):
            href = match.group("href").strip()
            label = re.sub(r"\s+", " ", (match.group("label") or "").strip())
            score = 0
            lower = f"{href} {label}".lower()
            if "zenodo" in lower:
                score += 4
            if "user stor" in lower:
                score += 6
            if "cirpass" in lower:
                score += 2
            if "v3.1" in lower:
                score += 2
            record_id = self._extract_zenodo_record_id(href)
            if record_id:
                score += 4
                links.append((score, href, record_id))

        if not links:
            direct_matches = re.findall(r"https://zenodo\.org/records/(\d+)", html)
            if direct_matches:
                record_id = max(direct_matches, key=int)
                record_url = f"https://zenodo.org/records/{record_id}"
                return record_url, record_id
            raise CirpassParseError("No official Zenodo record found in CIRPASS results page")

        links.sort(key=lambda item: (item[0], int(item[2])), reverse=True)
        _, href, record_id = links[0]
        record_url = f"https://zenodo.org/records/{record_id}"
        self._assert_url_allowed(href, allow_zenodo=True)
        return record_url, record_id

    def _select_pdf_url(self, record_payload: dict[str, object]) -> str:
        files = record_payload.get("files")
        if not isinstance(files, list):
            raise CirpassParseError("Zenodo record does not include files")

        candidates: list[tuple[int, str]] = []
        for file_obj in files:
            if not isinstance(file_obj, dict):
                continue
            key = str(file_obj.get("key", ""))
            if not key.lower().endswith(".pdf"):
                continue
            links = file_obj.get("links")
            href = ""
            if isinstance(links, dict):
                href = str(links.get("self") or links.get("download") or "")
            if not href:
                continue

            score = 1
            key_lower = key.lower()
            if "user" in key_lower and "stor" in key_lower:
                score += 6
            if "cirpass" in key_lower:
                score += 2
            if "v3" in key_lower:
                score += 1
            candidates.append((score, href))

        if not candidates:
            raise CirpassParseError("No PDF file found in Zenodo record")

        candidates.sort(key=lambda item: item[0], reverse=True)
        pdf_url = candidates[0][1]
        self._assert_url_allowed(pdf_url, allow_zenodo=True)
        return pdf_url

    def _extract_release_date(self, record_payload: dict[str, object]) -> str | None:
        metadata = record_payload.get("metadata")
        if not isinstance(metadata, dict):
            return None

        raw = metadata.get("publication_date") or metadata.get("date")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        created = record_payload.get("created")
        if isinstance(created, str) and created.strip():
            try:
                parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed.date().isoformat()

        return None

    def _extract_version(self, pdf_text: str, record_payload: dict[str, object]) -> str:
        candidates: list[str] = []

        for match in re.finditer(r"\bV\d+(?:\.\d+)?\b", pdf_text, flags=re.IGNORECASE):
            candidates.append(match.group(0).upper())

        metadata = record_payload.get("metadata")
        if isinstance(metadata, dict):
            title = str(metadata.get("title") or "")
            for match in re.finditer(r"\bV\d+(?:\.\d+)?\b", title, flags=re.IGNORECASE):
                candidates.append(match.group(0).upper())

        if not candidates:
            return "V3.1"

        def _version_key(version: str) -> tuple[int, ...]:
            numeric = version.lstrip("Vv")
            return tuple(int(part) for part in numeric.split("."))

        return max(candidates, key=_version_key)

    def _extract_level_stories(self, pdf_text: str) -> dict[str, list[CirpassStoryResponse]]:
        lines = [re.sub(r"\s+", " ", line).strip() for line in pdf_text.splitlines()]
        lines = [line for line in lines if line]

        extracted: list[CirpassStoryResponse] = []
        story_pattern = re.compile(
            r"^(?:user\s*story|us)\s*(?:#|no\.?|n°)?\s*([0-9]{1,2})?\s*[:\-–]?\s*(.+)$",
            flags=re.IGNORECASE,
        )

        for idx, line in enumerate(lines):
            match = story_pattern.match(line)
            if not match:
                continue
            story_num = match.group(1) or str(len(extracted) + 1)
            title = match.group(2).strip(" -:;")
            if not title:
                title = f"Story {story_num}"

            summary_bits: list[str] = []
            for next_line in lines[idx + 1 : idx + 4]:
                if story_pattern.match(next_line):
                    break
                summary_bits.append(next_line)
            summary = " ".join(summary_bits).strip() or title
            extracted.append(
                CirpassStoryResponse(
                    id=f"us-{story_num}",
                    title=title,
                    summary=summary,
                )
            )

        if not extracted:
            extracted = self._extract_story_candidates_from_sentences(pdf_text)

        buckets: dict[str, list[CirpassStoryResponse]] = {
            "create": [],
            "access": [],
            "update": [],
            "transfer": [],
            "deactivate": [],
        }

        for story in extracted:
            text = f"{story.title} {story.summary}".lower()
            scores: list[tuple[int, str]] = []
            for level, keywords in _LEVEL_KEYWORDS.items():
                score = sum(1 for keyword in keywords if keyword in text)
                scores.append((score, level))
            scores.sort(reverse=True)
            selected_level = scores[0][1] if scores and scores[0][0] > 0 else "create"
            if len(buckets[selected_level]) < 4:
                buckets[selected_level].append(story)

        for level, fallback in _FALLBACK_STORIES.items():
            if buckets[level]:
                continue
            buckets[level].append(
                CirpassStoryResponse(
                    id=f"{level}-fallback",
                    title=fallback[0],
                    summary=fallback[1],
                )
            )

        return buckets

    def _extract_story_candidates_from_sentences(self, pdf_text: str) -> list[CirpassStoryResponse]:
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", pdf_text))
        candidates: list[CirpassStoryResponse] = []
        for sentence in sentences:
            clean = sentence.strip()
            if len(clean) < 40 or len(clean) > 260:
                continue
            lowered = clean.lower()
            if "user story" not in lowered and "passport" not in lowered and "dpp" not in lowered:
                continue
            short_title = clean[:72].rstrip(" .,;:")
            candidates.append(
                CirpassStoryResponse(
                    id=f"sentence-{len(candidates) + 1}",
                    title=short_title,
                    summary=clean,
                )
            )
            if len(candidates) >= 15:
                break
        return candidates

    def _extract_zenodo_record_id(self, url: str) -> str | None:
        if not url:
            return None

        direct = re.search(r"zenodo\.org/records/(\d+)", url)
        if direct:
            return direct.group(1)

        doi = re.search(r"doi\.org/10\.5281/zenodo\.(\d+)", url)
        if doi:
            return doi.group(1)

        return None

    def _assert_url_allowed(self, url: str, allow_zenodo: bool) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in _ALLOWED_CIRPASS_HOSTS:
            return
        if allow_zenodo and host in _ALLOWED_ZENODO_HOSTS:
            return
        raise CirpassParseError(f"Non-official source is not allowed: {url}")


def iso_now() -> str:
    """UTC ISO helper used by service-level response generation."""
    return datetime.now(UTC).isoformat()
