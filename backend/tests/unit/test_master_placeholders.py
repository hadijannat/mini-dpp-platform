"""Tests for master placeholder utilities."""

from app.modules.masters.placeholders import (
    extract_placeholder_paths,
    json_pointer_to_path,
    resolve_json_pointer,
    set_json_pointer,
)


def test_extract_placeholder_paths_nested() -> None:
    payload = {
        "a": "{{Foo}}",
        "b": {"c": ["x", "{{Bar}}", {"d": "pre {{Foo}}"}]},
    }

    paths = extract_placeholder_paths(payload)

    assert paths["Foo"] == ["/a", "/b/c/2/d"]
    assert paths["Bar"] == ["/b/c/1"]


def test_json_pointer_to_path() -> None:
    assert json_pointer_to_path("") == "$"
    assert json_pointer_to_path("/a/b") == "$['a']['b']"
    assert json_pointer_to_path("/a/0/name") == "$['a'][0]['name']"


def test_resolve_and_set_pointer() -> None:
    payload = {"a": {"b": ["x", "y"]}}

    assert resolve_json_pointer(payload, "/a/b/1") == "y"
    assert set_json_pointer(payload, "/a/b/1", "z") is True
    assert resolve_json_pointer(payload, "/a/b/1") == "z"
