from specshift.protobuf_linter import lint_proto


def test_clean_proto3_schema_has_no_findings():
    proto = """
    syntax = "proto3";
    package bookstore.v1;

    message CreateUserRequest {
      string name = 1;
    }

    enum Role {
      ROLE_UNSPECIFIED = 0;
      ROLE_ADMIN = 1;
    }

    service UserService {
      rpc GetUser(GetUserRequest) returns (User);
    }
    """
    assert lint_proto(proto).is_empty


def test_missing_syntax_declaration_is_warning():
    result = lint_proto("message M { string id = 1; }")
    assert any(c.location == "syntax" for c in result.warnings)


def test_missing_package_declaration_is_info():
    result = lint_proto('syntax = "proto3"; message M { string id = 1; }')
    assert any(c.location == "package" for c in result.info_changes)


def test_reserved_field_number_range_is_breaking():
    result = lint_proto('syntax = "proto3"; message M { string id = 19500; }')
    assert result.has_breaking_changes
    assert any("19000" in c.message for c in result.breaking_changes)


def test_proto3_enum_first_value_not_zero_is_breaking():
    result = lint_proto('syntax = "proto3"; enum Role { ADMIN = 1; MEMBER = 2; }')
    assert result.has_breaking_changes
    assert any("must be zero" in c.message for c in result.breaking_changes)


def test_proto2_enum_first_value_not_zero_is_not_flagged():
    result = lint_proto('syntax = "proto2"; enum Role { ADMIN = 1; MEMBER = 2; }')
    assert not result.has_breaking_changes


def test_non_pascal_case_message_is_warning():
    result = lint_proto('syntax = "proto3"; message my_message { string id = 1; }')
    assert any("PascalCase" in c.message for c in result.warnings)


def test_non_snake_case_field_is_warning():
    result = lint_proto('syntax = "proto3"; message M { string userName = 1; }')
    assert any("lower_snake_case" in c.message for c in result.warnings)


def test_non_screaming_snake_enum_value_is_warning():
    result = lint_proto('syntax = "proto3"; enum Role { unspecified = 0; }')
    assert any("SCREAMING_SNAKE_CASE" in c.message for c in result.warnings)


def test_non_pascal_case_service_and_rpc_is_warning():
    result = lint_proto('syntax = "proto3"; service userservice { rpc get_user(Req) returns (Res); }')
    assert any("Service name" in c.message for c in result.warnings)
    assert any("RPC method name" in c.message for c in result.warnings)
