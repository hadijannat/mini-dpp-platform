"""Safe value transform DSL for OPC UA → AAS mapping.

Provides a pipe-delimited chain of simple operations that convert raw
OPC UA values into the format expected by AAS submodel properties.

Example expressions::

    "scale:0.001|round:2"          → multiply by 0.001, round to 2dp
    "cast:string"                  → convert to string
    "enum_map:{\"0\":\"OFF\"}"     → lookup in mapping dict
    "scale:1.8|offset:32|round:1"  → Celsius to Fahrenheit

Security: No ``eval``, no arbitrary code execution.  Only registered,
validated operations are permitted.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


class TransformError(Exception):
    """Raised when a transform operation fails at runtime."""


class TransformParseError(Exception):
    """Raised when a transform expression cannot be parsed."""


# ---------------------------------------------------------------------------
# Base class + registry
# ---------------------------------------------------------------------------

_OP_REGISTRY: dict[str, type[TransformOp]] = {}


class TransformOp(ABC):
    """Base class for a single transform operation."""

    @abstractmethod
    def apply(self, value: Any) -> Any:
        """Apply this operation to *value* and return the result."""

    @classmethod
    @abstractmethod
    def parse_arg(cls, arg: str) -> TransformOp:
        """Parse the argument string and return an instance."""

    @classmethod
    def register(cls, name: str) -> Callable[[type[TransformOp]], type[TransformOp]]:
        """Class decorator — register an op under *name*."""

        def decorator(klass: type[TransformOp]) -> type[TransformOp]:
            _OP_REGISTRY[name] = klass
            return klass

        return decorator


# ---------------------------------------------------------------------------
# Concrete operations
# ---------------------------------------------------------------------------


@TransformOp.register("cast")
class CastOp(TransformOp):
    """Cast value to a target type: number, int, bool, string."""

    _ALLOWED = frozenset({"number", "int", "bool", "string", "float"})

    def __init__(self, target: str) -> None:
        self.target = target

    def apply(self, value: Any) -> Any:
        try:
            if self.target in ("number", "float"):
                return float(value)
            if self.target == "int":
                return int(float(value))
            if self.target == "bool":
                if isinstance(value, str):
                    return value.lower() not in ("", "0", "false", "no", "null")
                return bool(value)
            # string
            return str(value)
        except (ValueError, TypeError) as exc:
            raise TransformError(f"cast:{self.target} failed for {value!r}") from exc

    @classmethod
    def parse_arg(cls, arg: str) -> CastOp:
        if arg not in cls._ALLOWED:
            raise TransformParseError(
                f"cast: unknown type '{arg}', expected one of {sorted(cls._ALLOWED)}"
            )
        return cls(arg)


@TransformOp.register("scale")
class ScaleOp(TransformOp):
    """Multiply value by a constant factor."""

    def __init__(self, factor: float) -> None:
        self.factor = factor

    def apply(self, value: Any) -> Any:
        try:
            return float(value) * self.factor
        except (ValueError, TypeError) as exc:
            raise TransformError(f"scale:{self.factor} failed for {value!r}") from exc

    @classmethod
    def parse_arg(cls, arg: str) -> ScaleOp:
        try:
            return cls(float(arg))
        except ValueError as exc:
            raise TransformParseError(f"scale: invalid factor '{arg}'") from exc


@TransformOp.register("offset")
class OffsetOp(TransformOp):
    """Add a constant offset to the value."""

    def __init__(self, offset: float) -> None:
        self.offset = offset

    def apply(self, value: Any) -> Any:
        try:
            return float(value) + self.offset
        except (ValueError, TypeError) as exc:
            raise TransformError(f"offset:{self.offset} failed for {value!r}") from exc

    @classmethod
    def parse_arg(cls, arg: str) -> OffsetOp:
        try:
            return cls(float(arg))
        except ValueError as exc:
            raise TransformParseError(f"offset: invalid value '{arg}'") from exc


@TransformOp.register("round")
class RoundOp(TransformOp):
    """Round numeric value to N decimal places."""

    def __init__(self, decimals: int) -> None:
        self.decimals = decimals

    def apply(self, value: Any) -> Any:
        try:
            return round(float(value), self.decimals)
        except (ValueError, TypeError) as exc:
            raise TransformError(f"round:{self.decimals} failed for {value!r}") from exc

    @classmethod
    def parse_arg(cls, arg: str) -> RoundOp:
        try:
            n = int(arg)
        except ValueError as exc:
            raise TransformParseError(f"round: invalid decimals '{arg}'") from exc
        if n < 0 or n > 15:
            raise TransformParseError(f"round: decimals must be 0-15, got {n}")
        return cls(n)


@TransformOp.register("enum_map")
class EnumMapOp(TransformOp):
    """Look up value in a JSON mapping dict."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def apply(self, value: Any) -> Any:
        key = str(value)
        if key not in self.mapping:
            raise TransformError(
                f"enum_map: key '{key}' not in mapping {list(self.mapping.keys())}"
            )
        return self.mapping[key]

    @classmethod
    def parse_arg(cls, arg: str) -> EnumMapOp:
        try:
            mapping = json.loads(arg)
        except json.JSONDecodeError as exc:
            raise TransformParseError(f"enum_map: invalid JSON '{arg}'") from exc
        if not isinstance(mapping, dict):
            raise TransformParseError("enum_map: argument must be a JSON object")
        # Ensure all keys and values are strings
        clean: dict[str, str] = {}
        for k, v in mapping.items():
            clean[str(k)] = str(v)
        return cls(clean)


@TransformOp.register("timestamp")
class TimestampOp(TransformOp):
    """Format a numeric/datetime value as a timestamp string."""

    _FORMATS = frozenset({"iso8601", "epoch_s", "epoch_ms"})

    def __init__(self, fmt: str) -> None:
        self.fmt = fmt

    def apply(self, value: Any) -> Any:
        try:
            if self.fmt == "iso8601":
                if isinstance(value, datetime):
                    return value.isoformat()
                if isinstance(value, (int, float)):
                    return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
                return str(value)
            if self.fmt == "epoch_s":
                if isinstance(value, datetime):
                    return value.timestamp()
                return float(value)
            if self.fmt == "epoch_ms":
                if isinstance(value, datetime):
                    return value.timestamp() * 1000
                return float(value) * 1000
        except (ValueError, TypeError, OSError) as exc:
            raise TransformError(f"timestamp:{self.fmt} failed for {value!r}") from exc
        return str(value)  # pragma: no cover — unreachable if _FORMATS correct

    @classmethod
    def parse_arg(cls, arg: str) -> TimestampOp:
        if arg not in cls._FORMATS:
            raise TransformParseError(
                f"timestamp: unknown format '{arg}', expected one of {sorted(cls._FORMATS)}"
            )
        return cls(arg)


@TransformOp.register("concat")
class ConcatOp(TransformOp):
    """Concatenate parts, using ``$value`` as a placeholder for the input.

    Example: ``concat:["prefix-","$value","-suffix"]``
    """

    def __init__(self, parts: list[str]) -> None:
        self.parts = parts

    def apply(self, value: Any) -> Any:
        result_parts: list[str] = []
        for part in self.parts:
            if part == "$value":
                result_parts.append(str(value))
            else:
                result_parts.append(part)
        return "".join(result_parts)

    @classmethod
    def parse_arg(cls, arg: str) -> ConcatOp:
        try:
            parts = json.loads(arg)
        except json.JSONDecodeError as exc:
            raise TransformParseError(f"concat: invalid JSON '{arg}'") from exc
        if not isinstance(parts, list):
            raise TransformParseError("concat: argument must be a JSON array")
        return cls([str(p) for p in parts])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_transform_expr(expr: str) -> list[TransformOp]:
    """Parse a pipe-delimited transform expression into a list of ops.

    Example::

        parse_transform_expr("scale:0.001|round:2")
        # → [ScaleOp(0.001), RoundOp(2)]

    Raises ``TransformParseError`` on invalid syntax.
    """
    if not expr or not expr.strip():
        raise TransformParseError("transform expression is empty")

    ops: list[TransformOp] = []
    for segment in expr.split("|"):
        segment = segment.strip()
        if not segment:
            continue

        # Split on first colon only — arg may contain colons (e.g. JSON)
        if ":" not in segment:
            raise TransformParseError(f"invalid segment '{segment}': expected 'op_name:arg'")
        op_name, arg = segment.split(":", 1)
        op_name = op_name.strip()
        arg = arg.strip()

        op_class = _OP_REGISTRY.get(op_name)
        if op_class is None:
            raise TransformParseError(
                f"unknown transform op '{op_name}', available: {sorted(_OP_REGISTRY.keys())}"
            )
        ops.append(op_class.parse_arg(arg))

    if not ops:
        raise TransformParseError("transform expression produced no operations")
    return ops


def apply_transform(expr: str, value: Any) -> Any:
    """Parse *expr* and apply the transform chain to *value*.

    Returns the final transformed value.
    Raises ``TransformError`` on runtime failures.
    """
    ops = parse_transform_expr(expr)
    result = value
    for op in ops:
        result = op.apply(result)
    return result


def validate_transform_expr(expr: str) -> list[str]:
    """Validate a transform expression without applying it.

    Returns a list of error messages.  Empty list means valid.
    """
    errors: list[str] = []
    try:
        parse_transform_expr(expr)
    except TransformParseError as exc:
        errors.append(str(exc))
    return errors
