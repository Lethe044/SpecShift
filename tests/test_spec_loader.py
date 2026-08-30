import json

import pytest

from specshift.spec_loader import SpecLoadError, load_spec, resolve_ref, resolve_schema


def test_load_spec_from_yaml_file(tmp_path):
    file_path = tmp_path / "spec.yaml"
    file_path.write_text(
        "openapi: 3.0.0\ninfo:\n  title: Demo\n  version: '1.0'\npaths: {}\n", encoding="utf-8"
    )
    spec = load_spec(str(file_path))
    assert spec["info"]["title"] == "Demo"


def test_load_spec_from_json_file(tmp_path):
    file_path = tmp_path / "spec.json"
    data = {"openapi": "3.0.0", "info": {"title": "Demo", "version": "1.0"}, "paths": {}}
    file_path.write_text(json.dumps(data), encoding="utf-8")
    spec = load_spec(str(file_path))
    assert spec["info"]["title"] == "Demo"


def test_load_spec_missing_source_raises():
    with pytest.raises(SpecLoadError):
        load_spec("does-not-exist.yaml")


def test_resolve_ref_finds_nested_schema():
    spec = {"components": {"schemas": {"User": {"type": "object", "properties": {"id": {"type": "string"}}}}}}
    resolved = resolve_ref("#/components/schemas/User", spec)
    assert resolved["type"] == "object"


def test_resolve_ref_unknown_returns_empty():
    spec = {"components": {"schemas": {}}}
    resolved = resolve_ref("#/components/schemas/Missing", spec)
    assert resolved == {}


def test_resolve_schema_follows_ref():
    spec = {
        "components": {"schemas": {"User": {"type": "object"}}},
    }
    schema = {"$ref": "#/components/schemas/User"}
    resolved = resolve_schema(schema, spec)
    assert resolved["type"] == "object"
