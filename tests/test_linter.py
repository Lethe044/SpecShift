from specshift.linter import lint_spec


def base_clean_spec():
    return {
        "info": {"title": "Clean API", "version": "1.0.0", "description": "A clean example API."},
        "paths": {
            "/users/{userId}": {
                "get": {
                    "operationId": "getUser",
                    "summary": "Get a user",
                    "parameters": [
                        {"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
                            },
                        },
                        "404": {"description": "Not found"},
                    },
                }
            }
        },
        "components": {"schemas": {"User": {"type": "object"}}},
    }


def test_clean_spec_has_no_findings():
    result = lint_spec(base_clean_spec())
    assert result.is_empty


def test_missing_info_description_is_info():
    spec = base_clean_spec()
    del spec["info"]["description"]
    result = lint_spec(spec)
    assert any(c.category == "lint_info" for c in result.info_changes)


def test_undeclared_path_parameter_is_breaking():
    spec = base_clean_spec()
    spec["paths"]["/users/{userId}"]["get"]["parameters"] = []
    result = lint_spec(spec)
    assert result.has_breaking_changes
    assert any("userId" in c.message for c in result.breaking_changes)


def test_path_parameter_not_required_is_breaking():
    spec = base_clean_spec()
    spec["paths"]["/users/{userId}"]["get"]["parameters"][0]["required"] = False
    result = lint_spec(spec)
    assert result.has_breaking_changes


def test_missing_response_description_is_breaking():
    spec = base_clean_spec()
    del spec["paths"]["/users/{userId}"]["get"]["responses"]["404"]["description"]
    result = lint_spec(spec)
    assert result.has_breaking_changes


def test_missing_operation_id_is_warning():
    spec = base_clean_spec()
    del spec["paths"]["/users/{userId}"]["get"]["operationId"]
    result = lint_spec(spec)
    assert not result.has_breaking_changes
    assert any(c.category == "lint_operation" for c in result.warnings)


def test_duplicate_operation_id_is_breaking():
    spec = base_clean_spec()
    spec["paths"]["/orders/{orderId}"] = {
        "get": {
            "operationId": "getUser",
            "summary": "Get an order",
            "parameters": [{"name": "orderId", "in": "path", "required": True, "schema": {"type": "string"}}],
            "responses": {"200": {"description": "ok"}},
        }
    }
    result = lint_spec(spec)
    assert result.has_breaking_changes
    assert any("getUser" in c.location for c in result.breaking_changes)


def test_missing_summary_is_warning():
    spec = base_clean_spec()
    del spec["paths"]["/users/{userId}"]["get"]["summary"]
    result = lint_spec(spec)
    assert any("summary" in c.message.lower() for c in result.warnings)


def test_missing_error_response_is_warning():
    spec = base_clean_spec()
    spec["paths"]["/users/{userId}"]["post"] = {
        "operationId": "createUser",
        "summary": "Create a user",
        "responses": {"201": {"description": "Created"}},
    }
    result = lint_spec(spec)
    assert any("error response" in c.message for c in result.warnings)


def test_undefined_security_scheme_is_breaking():
    spec = base_clean_spec()
    spec["paths"]["/users/{userId}"]["get"]["security"] = [{"ApiKeyAuth": []}]
    result = lint_spec(spec)
    assert result.has_breaking_changes
    assert any("ApiKeyAuth" in c.message for c in result.breaking_changes)


def test_defined_security_scheme_is_not_flagged():
    spec = base_clean_spec()
    spec["components"]["securitySchemes"] = {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-Key"}}
    spec["paths"]["/users/{userId}"]["get"]["security"] = [{"ApiKeyAuth": []}]
    result = lint_spec(spec)
    assert not result.has_breaking_changes


def test_unused_schema_is_info():
    spec = base_clean_spec()
    spec["components"]["schemas"]["Orphan"] = {"type": "object"}
    result = lint_spec(spec)
    assert any("Orphan" in c.location for c in result.info_changes)


def test_inconsistent_path_naming_is_warning():
    spec = base_clean_spec()
    spec["paths"]["/order_items"] = {
        "get": {
            "operationId": "listOrderItems",
            "summary": "List",
            "responses": {"200": {"description": "ok"}},
        }
    }
    spec["paths"]["/shippingAddresses"] = {
        "get": {
            "operationId": "listShippingAddresses",
            "summary": "List",
            "responses": {"200": {"description": "ok"}},
        }
    }
    spec["paths"]["/payment-methods"] = {
        "get": {
            "operationId": "listPaymentMethods",
            "summary": "List",
            "responses": {"200": {"description": "ok"}},
        }
    }
    result = lint_spec(spec)
    assert any(c.category == "lint_style" for c in result.warnings)


def test_single_naming_style_is_not_flagged():
    spec = base_clean_spec()
    spec["paths"]["/order-items"] = {
        "get": {
            "operationId": "listOrderItems",
            "summary": "List",
            "responses": {"200": {"description": "ok"}},
        }
    }
    result = lint_spec(spec)
    assert not any(c.category == "lint_style" for c in result.changes)
