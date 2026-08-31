from specshift.differ import diff_specs
from specshift.models import Severity


def base_spec(**overrides):
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                        "required": ["id"],
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
    }
    spec.update(overrides)
    return spec


def test_identical_specs_produce_no_changes():
    spec = base_spec()
    result = diff_specs(spec, spec)
    assert result.is_empty
    assert not result.has_breaking_changes


def test_removed_path_is_breaking():
    old = base_spec()
    new = base_spec(paths={})
    result = diff_specs(old, new)
    assert result.has_breaking_changes
    assert any("removed" in c.message for c in result.breaking_changes)


def test_added_path_is_info_only():
    old = base_spec()
    new = base_spec()
    new["paths"]["/other"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    result = diff_specs(old, new)
    assert not result.has_breaking_changes
    assert any(c.severity == Severity.INFO for c in result.changes)


def test_removed_response_field_is_breaking():
    old = base_spec()
    new = base_spec()
    del new["paths"]["/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"][
        "name"
    ]
    result = diff_specs(old, new)
    assert result.has_breaking_changes
    assert any("name" in c.location for c in result.breaking_changes)


def test_added_response_field_is_info():
    old = base_spec()
    new = base_spec()
    new["paths"]["/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"][
        "email"
    ] = {"type": "string"}
    result = diff_specs(old, new)
    assert not result.has_breaking_changes
    assert any("email" in c.location for c in result.changes)


def test_response_type_change_is_breaking():
    old = base_spec()
    new = base_spec()
    new["paths"]["/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"][
        "type"
    ] = "integer"
    result = diff_specs(old, new)
    assert result.has_breaking_changes


def test_new_required_request_field_is_breaking():
    old = {
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/items": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                    "required": ["name"],
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    new = {
        "info": {"title": "T", "version": "1.1"},
        "paths": {
            "/items": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "category": {"type": "string"},
                                    },
                                    "required": ["name", "category"],
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    result = diff_specs(old, new)
    assert result.has_breaking_changes
    assert any("category" in c.location for c in result.breaking_changes)


def test_new_optional_request_field_is_not_breaking():
    old = {
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/items": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {"name": {"type": "string"}}}
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    new = {
        "info": {"title": "T", "version": "1.1"},
        "paths": {
            "/items": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}, "note": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    result = diff_specs(old, new)
    assert not result.has_breaking_changes


def test_removed_required_parameter_is_breaking():
    old = base_spec()
    old["paths"]["/items"]["get"]["parameters"] = [
        {"name": "filter", "in": "query", "required": True, "schema": {"type": "string"}}
    ]
    new = base_spec()
    result = diff_specs(old, new)
    assert result.has_breaking_changes


def test_enum_value_removed_is_breaking():
    old = base_spec()
    old["paths"]["/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"][
        "status"
    ] = {"type": "string", "enum": ["active", "inactive"]}
    new = base_spec()
    new["paths"]["/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"][
        "status"
    ] = {"type": "string", "enum": ["active"]}
    result = diff_specs(old, new)
    assert result.has_breaking_changes


def test_example_specs_produce_expected_breaking_count():
    import yaml
    from pathlib import Path

    examples_dir = Path(__file__).parent.parent / "examples"
    old_spec = yaml.safe_load((examples_dir / "old_api.yaml").read_text(encoding="utf-8"))
    new_spec = yaml.safe_load((examples_dir / "new_api.yaml").read_text(encoding="utf-8"))

    result = diff_specs(old_spec, new_spec)

    assert result.has_breaking_changes
    counts = result.summary_counts()
    assert counts["breaking"] >= 5
    assert counts["info"] >= 1
