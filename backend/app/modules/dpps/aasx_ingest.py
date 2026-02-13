"""AASX ingestion helpers for deterministic import flows."""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import posixpath
import zipfile
from dataclasses import dataclass
from typing import Any

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json


@dataclass(frozen=True)
class SupplementaryFile:
    """Supplementary file extracted from an AASX package."""

    package_path: str
    content_type: str
    payload: bytes
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class AasxIngestResult:
    """Parsed AASX package payload."""

    aas_env_json: dict[str, Any]
    supplementary_files: list[SupplementaryFile]
    doc_hints_manifest: dict[str, Any] | None


class AasxIngestService:
    """Read AASX packages into canonical environment + supplementary payloads."""

    DOC_HINTS_PATH = "/aasx/files/ui-hints.json"

    def parse(self, aasx_bytes: bytes) -> AasxIngestResult:
        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
        with aasx.AASXReader(io.BytesIO(aasx_bytes)) as reader:
            reader.read_into(store, files)

        env_json_raw = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
        if isinstance(env_json_raw, str):
            aas_env_json = json.loads(env_json_raw)
        elif isinstance(env_json_raw, dict):
            aas_env_json = env_json_raw
        else:
            raise ValueError("Unexpected AAS environment payload type while parsing AASX")

        extracted_files = self._extract_supplementary_files(files, aasx_bytes)
        doc_hints_manifest = self._extract_doc_hints_manifest(extracted_files)
        return AasxIngestResult(
            aas_env_json=aas_env_json,
            supplementary_files=extracted_files,
            doc_hints_manifest=doc_hints_manifest,
        )

    def _extract_supplementary_files(
        self,
        files: aasx.DictSupplementaryFileContainer,
        aasx_bytes: bytes,
    ) -> list[SupplementaryFile]:
        entries: dict[str, SupplementaryFile] = {}
        for name in sorted(files):
            package_path = self._normalize_package_path(name)
            if package_path is None:
                continue
            output = io.BytesIO()
            files.write_file(name, output)
            payload = output.getvalue()
            content_type = files.get_content_type(name) or "application/octet-stream"
            entries[package_path] = SupplementaryFile(
                package_path=package_path,
                content_type=content_type,
                payload=payload,
                sha256=hashlib.sha256(payload).hexdigest(),
            )

        # Read raw ZIP entries as fallback so sidecar docs are captured even when
        # not explicitly referenced by File/Blob elements.
        with zipfile.ZipFile(io.BytesIO(aasx_bytes), "r") as archive:
            for name in sorted(archive.namelist()):
                package_path = self._normalize_package_path(name)
                if package_path is None:
                    continue
                if package_path in entries:
                    continue
                payload = archive.read(name)
                guessed_type = mimetypes.guess_type(package_path, strict=False)[0]
                entries[package_path] = SupplementaryFile(
                    package_path=package_path,
                    content_type=guessed_type or "application/octet-stream",
                    payload=payload,
                    sha256=hashlib.sha256(payload).hexdigest(),
                )

        return [entries[key] for key in sorted(entries.keys())]

    def _extract_doc_hints_manifest(
        self, supplementary_files: list[SupplementaryFile]
    ) -> dict[str, Any] | None:
        sidecar = None
        for file in supplementary_files:
            normalized = file.package_path.replace("\\", "/")
            if normalized == self.DOC_HINTS_PATH or normalized.endswith("/ui-hints.json"):
                sidecar = file
                break
        if sidecar is None:
            return None

        try:
            payload = json.loads(sidecar.payload.decode("utf-8"))
        except Exception as exc:
            raise ValueError("Invalid ui-hints.json content in AASX package") from exc

        manifest = self._normalize_doc_hints(payload)
        manifest["source_path"] = sidecar.package_path
        manifest["source_sha256"] = sidecar.sha256
        return manifest

    def _normalize_doc_hints(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("ui-hints.json must be a JSON object")
        mappings = payload.get("mappings")
        if not isinstance(mappings, dict):
            raise ValueError("ui-hints.json must contain a 'mappings' object")

        by_semantic_id: dict[str, dict[str, Any]] = {}
        by_id_short_path: dict[str, dict[str, Any]] = {}

        for raw_key, raw_value in mappings.items():
            if not isinstance(raw_key, str):
                raise ValueError("ui-hints mappings keys must be strings")
            if not isinstance(raw_value, dict):
                raise ValueError(f"ui-hints entry '{raw_key}' must be an object")

            normalized_key = raw_key.strip()
            semantic_id = str(raw_value.get("semanticId") or "").strip()
            id_short_path = str(raw_value.get("idShortPath") or "").strip()
            entry = {
                "semanticId": semantic_id or None,
                "idShortPath": id_short_path or None,
                "helpText": raw_value.get("helpText"),
                "formUrl": raw_value.get("formUrl"),
                "pdfRef": raw_value.get("pdfRef"),
                "page": raw_value.get("page"),
                "key": normalized_key,
            }

            if semantic_id:
                semantic_key = semantic_id.rstrip("/").lower()
                if semantic_key in by_semantic_id:
                    raise ValueError(f"Ambiguous ui-hints mapping for semanticId '{semantic_id}'")
                by_semantic_id[semantic_key] = entry
            if id_short_path:
                path_key = id_short_path.strip("/")
                if path_key in by_id_short_path:
                    raise ValueError(
                        f"Ambiguous ui-hints mapping for idShortPath '{id_short_path}'"
                    )
                by_id_short_path[path_key] = entry
            if not semantic_id and not id_short_path:
                raise ValueError(
                    f"ui-hints mapping '{normalized_key}' must provide semanticId or idShortPath"
                )

        return {
            "by_semantic_id": dict(sorted(by_semantic_id.items())),
            "by_id_short_path": dict(sorted(by_id_short_path.items())),
        }

    def _normalize_package_path(self, raw_path: Any) -> str | None:
        if not isinstance(raw_path, str):
            return None
        path = raw_path.replace("\\", "/").strip()
        if not path:
            return None
        if not path.startswith("/"):
            path = f"/{path}"
        normalized = posixpath.normpath(path)
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if normalized in {"/", "/."}:
            return None
        if not normalized.startswith("/aasx/files/"):
            return None
        return normalized
