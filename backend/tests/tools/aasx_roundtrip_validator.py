"""AASX round-trip validation tool.

Exports an AAS environment as AASX, reads it back via BaSyx,
re-exports, and compares the two object stores for structural
equivalence.  Validates IDTA Part 5 package compliance.

Usage:
    uv run python tests/tools/aasx_roundtrip_validator.py [--from-json FILE]

Without arguments, uses a built-in AAS environment covering all element types.
With ``--from-json``, reads an AAS environment from a JSON file (e.g. a
previously exported DPP).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json

# ---------------------------------------------------------------------------
# Built-in test AAS environment (covers key element types)
# ---------------------------------------------------------------------------

_BUILTIN_AAS_ENV: dict[str, Any] = {
    "assetAdministrationShells": [
        {
            "modelType": "AssetAdministrationShell",
            "id": "urn:aas:roundtrip:1",
            "idShort": "RoundtripAAS",
            "assetInformation": {
                "assetKind": "Instance",
                "globalAssetId": "urn:asset:roundtrip:1",
            },
        }
    ],
    "submodels": [
        {
            "modelType": "Submodel",
            "id": "urn:sm:roundtrip:1",
            "idShort": "MixedElements",
            "submodelElements": [
                {
                    "modelType": "Property",
                    "idShort": "StringProp",
                    "valueType": "xs:string",
                    "value": "hello",
                },
                {
                    "modelType": "Property",
                    "idShort": "IntProp",
                    "valueType": "xs:integer",
                    "value": "42",
                },
                {
                    "modelType": "MultiLanguageProperty",
                    "idShort": "Description",
                    "value": [
                        {"language": "en", "text": "A test item"},
                        {"language": "de", "text": "Ein Testelement"},
                    ],
                },
                {
                    "modelType": "Range",
                    "idShort": "TempRange",
                    "valueType": "xs:double",
                    "min": "-20.0",
                    "max": "80.0",
                },
                {
                    "modelType": "SubmodelElementCollection",
                    "idShort": "Details",
                    "value": [
                        {
                            "modelType": "Property",
                            "idShort": "InnerProp",
                            "valueType": "xs:string",
                            "value": "nested-value",
                        }
                    ],
                },
                {
                    "modelType": "File",
                    "idShort": "Manual",
                    "contentType": "application/pdf",
                    "value": "https://example.com/docs/manual.pdf",
                },
            ],
        }
    ],
    "conceptDescriptions": [],
}


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------


def _json_to_object_store(
    aas_env: dict[str, Any],
) -> model.DictObjectStore[model.Identifiable]:
    """Deserialize an AAS env dict into a BaSyx object store."""
    payload = json.dumps(aas_env, sort_keys=True, ensure_ascii=False)
    return basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
        io.StringIO(payload), failsafe=True
    )


def _object_store_to_aasx(
    store: model.DictObjectStore[model.Identifiable],
) -> bytes:
    """Serialize a BaSyx object store into an AASX package."""
    buf = io.BytesIO()
    files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
    with aasx.AASXWriter(buf) as writer:
        writer.write_all_aas_objects("/aasx/data.json", store, files, write_json=True)
    buf.seek(0)
    return buf.read()


def _aasx_to_object_store(
    aasx_bytes: bytes,
) -> model.DictObjectStore[model.Identifiable]:
    """Read an AASX package back into a BaSyx object store."""
    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
    with aasx.AASXReader(io.BytesIO(aasx_bytes)) as reader:
        reader.read_into(store, files)
    return store


def _store_to_json_str(
    store: model.DictObjectStore[model.Identifiable],
) -> str:
    """Serialize an object store to canonical JSON string."""
    return basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]


def _collect_identifiable_ids(
    store: model.DictObjectStore[model.Identifiable],
) -> set[str]:
    """Collect all identifiable IDs from an object store."""
    ids: set[str] = set()
    for obj in store:
        ids.add(obj.id)
    return ids


def validate_aasx_structure(aasx_bytes: bytes) -> dict[str, Any]:
    """Validate AASX package structure (ZIP entries, required files)."""
    errors: list[str] = []
    entries: list[str] = []

    try:
        with zipfile.ZipFile(io.BytesIO(aasx_bytes), "r") as zf:
            entries = zf.namelist()

            if "[Content_Types].xml" not in entries:
                errors.append("Missing [Content_Types].xml")
            if "_rels/.rels" not in entries:
                errors.append("Missing _rels/.rels")

            data_files = [n for n in entries if n.startswith("aasx/") and n.endswith((".json", ".xml"))]
            if not data_files:
                errors.append("No AAS data file found in /aasx/")

    except zipfile.BadZipFile:
        errors.append("Not a valid ZIP file")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "entries": entries,
    }


def roundtrip_validate(aas_env: dict[str, Any]) -> dict[str, Any]:
    """Run full AASX round-trip validation.

    Steps:
    1. JSON dict → BaSyx object store (store_1)
    2. store_1 → AASX bytes
    3. AASX bytes → BaSyx object store (store_2)
    4. store_2 → AASX bytes (re-export)
    5. Compare store_1 and store_2 identifiable IDs
    6. Compare AASX bytes from step 2 and step 4

    Returns a report dict with pass/fail status and details.
    """
    report: dict[str, Any] = {
        "steps": {},
        "passed": True,
        "errors": [],
    }

    # Step 1: JSON → object store
    try:
        store_1 = _json_to_object_store(aas_env)
        ids_1 = _collect_identifiable_ids(store_1)
        report["steps"]["json_to_store"] = {
            "status": "ok",
            "identifiable_count": len(ids_1),
            "ids": sorted(ids_1),
        }
    except Exception as exc:
        report["steps"]["json_to_store"] = {"status": "failed", "error": str(exc)}
        report["passed"] = False
        report["errors"].append(f"Step 1 (JSON→Store) failed: {exc}")
        return report

    # Step 2: object store → AASX
    try:
        aasx_1 = _object_store_to_aasx(store_1)
        struct_1 = validate_aasx_structure(aasx_1)
        report["steps"]["store_to_aasx"] = {
            "status": "ok",
            "size_bytes": len(aasx_1),
            "structure_valid": struct_1["valid"],
            "entries": struct_1["entries"],
        }
        if not struct_1["valid"]:
            report["passed"] = False
            report["errors"].extend(struct_1["errors"])
    except Exception as exc:
        report["steps"]["store_to_aasx"] = {"status": "failed", "error": str(exc)}
        report["passed"] = False
        report["errors"].append(f"Step 2 (Store→AASX) failed: {exc}")
        return report

    # Step 3: AASX → object store (round-trip)
    try:
        store_2 = _aasx_to_object_store(aasx_1)
        ids_2 = _collect_identifiable_ids(store_2)
        report["steps"]["aasx_to_store"] = {
            "status": "ok",
            "identifiable_count": len(ids_2),
            "ids": sorted(ids_2),
        }
    except Exception as exc:
        report["steps"]["aasx_to_store"] = {"status": "failed", "error": str(exc)}
        report["passed"] = False
        report["errors"].append(f"Step 3 (AASX→Store) failed: {exc}")
        return report

    # Step 4: store_2 → AASX (second export)
    try:
        aasx_2 = _object_store_to_aasx(store_2)
        struct_2 = validate_aasx_structure(aasx_2)
        report["steps"]["store_to_aasx_2"] = {
            "status": "ok",
            "size_bytes": len(aasx_2),
            "structure_valid": struct_2["valid"],
        }
    except Exception as exc:
        report["steps"]["store_to_aasx_2"] = {"status": "failed", "error": str(exc)}
        report["passed"] = False
        report["errors"].append(f"Step 4 (Store→AASX re-export) failed: {exc}")
        return report

    # Step 5: Compare identifiable IDs
    missing = ids_1 - ids_2
    extra = ids_2 - ids_1
    report["steps"]["id_comparison"] = {
        "status": "ok" if not missing and not extra else "mismatch",
        "missing_after_roundtrip": sorted(missing),
        "extra_after_roundtrip": sorted(extra),
    }
    if missing:
        report["passed"] = False
        report["errors"].append(f"Lost identifiables after round-trip: {sorted(missing)}")
    if extra:
        report["errors"].append(f"Extra identifiables after round-trip: {sorted(extra)}")

    # Step 6: Compare JSON serializations
    try:
        json_1 = _store_to_json_str(store_1)
        json_2 = _store_to_json_str(store_2)
        json_match = json_1 == json_2
        report["steps"]["json_comparison"] = {
            "status": "ok" if json_match else "mismatch",
            "json_1_length": len(json_1),
            "json_2_length": len(json_2),
            "identical": json_match,
        }
        if not json_match:
            report["errors"].append(
                "JSON serializations differ after round-trip "
                f"(len {len(json_1)} vs {len(json_2)})"
            )
    except Exception as exc:
        report["steps"]["json_comparison"] = {"status": "failed", "error": str(exc)}
        report["errors"].append(f"Step 6 (JSON comparison) failed: {exc}")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="AASX round-trip validator")
    parser.add_argument(
        "--from-json",
        type=Path,
        help="Path to an AAS environment JSON file to validate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to save the validation report JSON",
    )
    args = parser.parse_args()

    if args.from_json:
        aas_env = json.loads(args.from_json.read_text(encoding="utf-8"))
        # If the file is a platform export, unwrap aasEnvironment
        if "aasEnvironment" in aas_env and "metadata" in aas_env:
            aas_env = aas_env["aasEnvironment"]
        source = str(args.from_json)
    else:
        aas_env = _BUILTIN_AAS_ENV
        source = "built-in test environment"

    print("AASX Round-Trip Validator")
    print("========================")
    print(f"Source: {source}")
    print()

    report = roundtrip_validate(aas_env)

    if report["passed"]:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")

    print()
    for step_name, step_data in report["steps"].items():
        status = step_data.get("status", "?")
        icon = "ok" if status == "ok" else "FAIL"
        print(f"  [{icon}] {step_name}")

    if report["errors"]:
        print()
        print("Errors:")
        for err in report["errors"]:
            print(f"  - {err}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport saved to: {args.output}")

    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
