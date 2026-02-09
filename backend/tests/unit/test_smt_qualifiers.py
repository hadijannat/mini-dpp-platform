"""Unit tests for SMT qualifier parsing utilities (qualifiers.py)."""

from __future__ import annotations

from app.modules.templates.qualifiers import (
    SmtQualifiers,
    _parse_allowed_range_value,
    _string_value,
    parse_smt_qualifiers,
)


class TestStringValue:
    def test_none_passthrough(self) -> None:
        assert _string_value(None) is None

    def test_strips_whitespace_from_string(self) -> None:
        assert _string_value("  hello  ") == "hello"

    def test_strips_whitespace_from_non_string(self) -> None:
        assert _string_value(42) == "42"

    def test_strips_whitespace_from_stringified_non_string(self) -> None:
        # Object whose str() has trailing space
        class Spaced:
            def __str__(self) -> str:
                return "  spaced  "

        assert _string_value(Spaced()) == "spaced"

    def test_empty_string_becomes_empty(self) -> None:
        assert _string_value("   ") == ""

    def test_normal_string_unchanged(self) -> None:
        assert _string_value("clean") == "clean"


class TestAllowedRange:
    def test_normal_range(self) -> None:
        result = _parse_allowed_range_value("0..100")
        assert result is not None
        assert result.min == 0.0
        assert result.max == 100.0
        assert result.raw == "0..100"

    def test_inverted_range_degrades_to_raw(self) -> None:
        result = _parse_allowed_range_value("100..0")
        assert result is not None
        assert result.min is None
        assert result.max is None
        assert result.raw == "100..0"

    def test_equal_range(self) -> None:
        result = _parse_allowed_range_value("5..5")
        assert result is not None
        assert result.min == 5.0
        assert result.max == 5.0

    def test_negative_range(self) -> None:
        result = _parse_allowed_range_value("-40..85")
        assert result is not None
        assert result.min == -40.0
        assert result.max == 85.0

    def test_decimal_range(self) -> None:
        result = _parse_allowed_range_value("0.5..99.9")
        assert result is not None
        assert result.min == 0.5
        assert result.max == 99.9

    def test_none_returns_none(self) -> None:
        assert _parse_allowed_range_value(None) is None

    def test_unparseable_returns_raw_only(self) -> None:
        result = _parse_allowed_range_value("not-a-range")
        assert result is not None
        assert result.min is None
        assert result.max is None
        assert result.raw == "not-a-range"


class TestParseSMTQualifiers:
    def test_strips_string_values(self) -> None:
        qualifiers = [
            {
                "type": "SMT/ExampleValue",
                "value": "  example  ",
            }
        ]
        result = parse_smt_qualifiers(qualifiers)
        assert result.example_value == "example"

    def test_strips_default_value(self) -> None:
        qualifiers = [
            {
                "type": "SMT/DefaultValue",
                "value": "  default  ",
            }
        ]
        result = parse_smt_qualifiers(qualifiers)
        assert result.default_value == "default"

    def test_strips_initial_value(self) -> None:
        qualifiers = [
            {
                "type": "SMT/InitialValue",
                "value": "  initial  ",
            }
        ]
        result = parse_smt_qualifiers(qualifiers)
        assert result.initial_value == "initial"

    def test_empty_qualifiers_returns_defaults(self) -> None:
        result = parse_smt_qualifiers(None)
        assert result == SmtQualifiers()

    def test_allowed_range_inverted_does_not_set_min_max(self) -> None:
        qualifiers = [
            {
                "type": "SMT/AllowedRange",
                "value": "100..0",
            }
        ]
        result = parse_smt_qualifiers(qualifiers)
        assert result.allowed_range is not None
        assert result.allowed_range.min is None
        assert result.allowed_range.max is None
        assert result.allowed_range.raw == "100..0"
