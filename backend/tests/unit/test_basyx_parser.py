"""Tests for BaSyx template parser strict mode enforcement."""

from __future__ import annotations

import json

import pytest

from app.modules.templates.basyx_parser import BasyxTemplateParser


class TestBasyxParserStrictMode:
    """Verify BaSyx parser raises on malformed input."""

    def setup_method(self) -> None:
        self.parser = BasyxTemplateParser()

    def test_valid_json_parses_successfully(self) -> None:
        """Valid minimal AAS environment parses without error."""
        env = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "id": "urn:example:submodel:1",
                    "modelType": "Submodel",
                    "submodelElements": [],
                }
            ],
            "conceptDescriptions": [],
        }
        payload = json.dumps(env).encode("utf-8")
        result = self.parser.parse_json(payload)
        assert result.submodel is not None

    def test_empty_json_object_raises(self) -> None:
        """Empty JSON object should raise ValueError."""
        payload = b"{}"
        with pytest.raises(ValueError):
            self.parser.parse_json(payload)

    def test_invalid_utf8_raises(self) -> None:
        """Non-UTF-8 bytes should raise ValueError."""
        payload = b"\xff\xfe"
        with pytest.raises(ValueError, match="not valid UTF-8"):
            self.parser.parse_json(payload)

    def test_malformed_json_raises(self) -> None:
        """Malformed JSON string should raise."""
        payload = b"not json at all"
        with pytest.raises((ValueError, Exception)):
            self.parser.parse_json(payload)

    def test_missing_submodels_raises(self) -> None:
        """Environment with no submodels should raise ValueError."""
        env = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }
        payload = json.dumps(env).encode("utf-8")
        with pytest.raises(ValueError, match="No Submodel found"):
            self.parser.parse_json(payload)
