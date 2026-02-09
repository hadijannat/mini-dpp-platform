"""Tests for template provenance tracking in DPP revisions."""

from __future__ import annotations


class TestTemplateProvenanceStructure:
    """Verify provenance metadata structure."""

    def test_provenance_keys_match_template_keys(self) -> None:
        """Provenance dict should have one entry per template key."""
        expected_fields = {
            "idta_version",
            "semantic_id",
            "resolved_version",
            "source_file_sha",
            "source_file_path",
            "source_kind",
            "selection_strategy",
        }
        entry = {
            "idta_version": "3.0.1",
            "semantic_id": "https://admin-shell.io/idta/SubmodelTemplate/Nameplate/3/0",
            "resolved_version": "V3.0.1",
            "source_file_sha": "abc123",
            "source_file_path": "path/to/file.json",
            "source_kind": "json",
            "selection_strategy": "exact_match_json",
        }
        assert set(entry.keys()) == expected_fields

    def test_provenance_allows_null_values(self) -> None:
        """Provenance should allow None for optional fields."""
        entry = {
            "idta_version": "3.0.1",
            "semantic_id": "https://example.com/sm",
            "resolved_version": None,
            "source_file_sha": None,
            "source_file_path": None,
            "source_kind": None,
            "selection_strategy": None,
        }
        assert len(entry) == 7
        assert entry["resolved_version"] is None
