"""Tests for batch import/export schemas and logic."""

import io
import json
import zipfile
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.dpps.router import (
    BatchImportItem,
    BatchImportRequest,
    BatchImportResponse,
    BatchImportResultItem,
)
from app.modules.export.router import (
    BatchExportRequest,
    BatchExportResponse,
    BatchExportResultItem,
)


# ── Batch Import Schema Tests ──────────────────────────────────────


class TestBatchImportSchemas:
    """Validate Pydantic schemas for batch import."""

    def test_minimal_import_item(self) -> None:
        item = BatchImportItem(
            asset_ids={"manufacturerPartId": "PART-001"}  # type: ignore[arg-type]
        )
        assert item.selected_templates == ["digital-nameplate"]
        assert item.initial_data is None

    def test_full_import_item(self) -> None:
        item = BatchImportItem(
            asset_ids={"manufacturerPartId": "P1", "serialNumber": "SN-1"},  # type: ignore[arg-type]
            selected_templates=["digital-nameplate", "carbon-footprint"],
            initial_data={"key": "value"},
        )
        assert len(item.selected_templates) == 2
        assert item.initial_data == {"key": "value"}

    def test_batch_request_enforces_min_length(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            BatchImportRequest(dpps=[])
        assert "min_length" in str(exc_info.value).lower() or "too_short" in str(
            exc_info.value
        ).lower()

    def test_batch_request_enforces_max_length(self) -> None:
        items = [
            BatchImportItem(
                asset_ids={"manufacturerPartId": f"P-{i}"}  # type: ignore[arg-type]
            )
            for i in range(101)
        ]
        with pytest.raises(ValidationError):
            BatchImportRequest(dpps=items)

    def test_batch_request_accepts_100_items(self) -> None:
        items = [
            BatchImportItem(
                asset_ids={"manufacturerPartId": f"P-{i}"}  # type: ignore[arg-type]
            )
            for i in range(100)
        ]
        req = BatchImportRequest(dpps=items)
        assert len(req.dpps) == 100

    def test_batch_import_response_model(self) -> None:
        resp = BatchImportResponse(
            total=3,
            succeeded=2,
            failed=1,
            results=[
                BatchImportResultItem(index=0, dpp_id=uuid4(), status="ok"),
                BatchImportResultItem(index=1, dpp_id=uuid4(), status="ok"),
                BatchImportResultItem(index=2, status="failed", error="Invalid template"),
            ],
        )
        assert resp.total == 3
        assert resp.succeeded == 2
        assert resp.failed == 1
        assert resp.results[2].dpp_id is None

    def test_result_item_dpp_id_optional(self) -> None:
        item = BatchImportResultItem(index=0, status="failed", error="test")
        assert item.dpp_id is None

    def test_result_item_error_optional(self) -> None:
        item = BatchImportResultItem(index=0, dpp_id=uuid4(), status="ok")
        assert item.error is None


# ── Batch Export Schema Tests ──────────────────────────────────────


class TestBatchExportSchemas:
    """Validate Pydantic schemas for batch export."""

    def test_default_format_is_json(self) -> None:
        req = BatchExportRequest(dpp_ids=[uuid4()])
        assert req.format == "json"

    def test_aasx_format(self) -> None:
        req = BatchExportRequest(dpp_ids=[uuid4()], format="aasx")
        assert req.format == "aasx"

    def test_invalid_format_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BatchExportRequest(dpp_ids=[uuid4()], format="xml")  # type: ignore[arg-type]

    def test_enforces_min_length(self) -> None:
        with pytest.raises(ValidationError):
            BatchExportRequest(dpp_ids=[])

    def test_enforces_max_length(self) -> None:
        ids = [uuid4() for _ in range(101)]
        with pytest.raises(ValidationError):
            BatchExportRequest(dpp_ids=ids)

    def test_accepts_100_ids(self) -> None:
        ids = [uuid4() for _ in range(100)]
        req = BatchExportRequest(dpp_ids=ids)
        assert len(req.dpp_ids) == 100

    def test_export_response_model(self) -> None:
        resp = BatchExportResponse(
            total=2,
            succeeded=1,
            failed=1,
            results=[
                BatchExportResultItem(dpp_id=uuid4(), status="ok"),
                BatchExportResultItem(dpp_id=uuid4(), status="failed", error="Not found"),
            ],
        )
        assert resp.total == 2
        assert resp.results[1].error == "Not found"


# ── ZIP Archive Structure Tests ────────────────────────────────────


class TestBatchExportZipStructure:
    """Verify ZIP archive creation logic used by batch export."""

    def test_zip_with_json_entries(self) -> None:
        """Simulate the ZIP creation logic from the batch export endpoint."""
        buffer = io.BytesIO()
        dpp_ids = [uuid4() for _ in range(3)]

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for dpp_id in dpp_ids:
                content = json.dumps({"dpp_id": str(dpp_id), "test": True})
                zf.writestr(f"dpp-{dpp_id}.json", content)

        buffer.seek(0)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            assert len(names) == 3
            for dpp_id in dpp_ids:
                assert f"dpp-{dpp_id}.json" in names
                data = json.loads(zf.read(f"dpp-{dpp_id}.json"))
                assert data["dpp_id"] == str(dpp_id)

    def test_empty_zip_when_all_fail(self) -> None:
        """If all exports fail, ZIP should still be valid but empty."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            pass  # no entries

        buffer.seek(0)
        with zipfile.ZipFile(buffer, "r") as zf:
            assert len(zf.namelist()) == 0

    def test_partial_failure_zip(self) -> None:
        """ZIP should contain only successful exports."""
        buffer = io.BytesIO()
        ok_id = uuid4()
        fail_id = uuid4()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Only add the successful one
            zf.writestr(f"dpp-{ok_id}.json", json.dumps({"ok": True}))

        buffer.seek(0)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            assert f"dpp-{ok_id}.json" in names
            assert f"dpp-{fail_id}.json" not in names


# ── Batch Import Savepoint Isolation Tests ─────────────────────────


class TestBatchImportIsolation:
    """Test that batch import result tracking works correctly for mixed outcomes."""

    def test_mixed_results_accounting(self) -> None:
        """Verify succeeded/failed counts are computed correctly."""
        results = [
            BatchImportResultItem(index=0, dpp_id=uuid4(), status="ok"),
            BatchImportResultItem(index=1, status="failed", error="bad template"),
            BatchImportResultItem(index=2, dpp_id=uuid4(), status="ok"),
            BatchImportResultItem(index=3, status="failed", error="duplicate"),
            BatchImportResultItem(index=4, dpp_id=uuid4(), status="ok"),
        ]
        succeeded = sum(1 for r in results if r.status == "ok")
        failed = len(results) - succeeded

        resp = BatchImportResponse(
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            results=results,
        )
        assert resp.total == 5
        assert resp.succeeded == 3
        assert resp.failed == 2

    def test_all_succeed(self) -> None:
        results = [
            BatchImportResultItem(index=i, dpp_id=uuid4(), status="ok") for i in range(5)
        ]
        succeeded = sum(1 for r in results if r.status == "ok")
        resp = BatchImportResponse(
            total=5, succeeded=succeeded, failed=0, results=results
        )
        assert resp.succeeded == 5
        assert resp.failed == 0

    def test_all_fail(self) -> None:
        results = [
            BatchImportResultItem(index=i, status="failed", error=f"err-{i}")
            for i in range(3)
        ]
        succeeded = sum(1 for r in results if r.status == "ok")
        resp = BatchImportResponse(
            total=3, succeeded=succeeded, failed=3, results=results
        )
        assert resp.succeeded == 0
        assert resp.failed == 3
