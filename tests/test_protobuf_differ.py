from specshift.protobuf_differ import diff_protos, parse_proto


def test_parse_proto_extracts_messages_enums_and_services():
    proto = """
    syntax = "proto3";

    message User {
      string id = 1;
      int32 age = 2;
    }

    enum Role {
      ADMIN = 0;
      MEMBER = 1;
    }

    service UserService {
      rpc GetUser(GetUserRequest) returns (User);
    }
    """
    defs = parse_proto(proto)
    assert defs["syntax"] == "proto3"
    assert set(defs["messages"].keys()) == {"User"}
    assert defs["messages"]["User"]["fields"]["id"]["number"] == 1
    assert defs["messages"]["User"]["fields"]["age"]["type"] == "int32"
    assert defs["enums"]["Role"]["values"] == {"ADMIN": 0, "MEMBER": 1}
    assert "GetUser" in defs["services"]["UserService"]["methods"]


def test_oneof_fields_are_parsed():
    proto = """
    message M {
      oneof contact {
        string email = 1;
        string phone = 2;
      }
      string name = 3;
    }
    """
    defs = parse_proto(proto)
    fields = defs["messages"]["M"]["fields"]
    assert set(fields.keys()) == {"email", "phone", "name"}


def test_identical_schemas_produce_no_changes():
    proto = "message M { string id = 1; }"
    result = diff_protos(proto, proto)
    assert result.is_empty


def test_removed_message_is_breaking():
    old = "message M { string id = 1; } message Legacy { string id = 1; }"
    new = "message M { string id = 1; }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes
    assert any(c.location == "Legacy" for c in result.breaking_changes)


def test_new_field_is_always_info_even_without_default() -> None:
    old = "message M { string id = 1; }"
    new = "message M { string id = 1; int32 age = 2; }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes
    assert any(c.severity.value == "info" for c in result.changes)


def test_field_number_change_is_breaking():
    old = "message M { string id = 1; }"
    new = "message M { string id = 2; }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes


def test_field_number_reused_with_different_type_is_breaking():
    old = "message M { string old_field = 5; }"
    new = "message M { int32 new_field = 5; }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes
    assert any("misinterpreted" in c.message for c in result.breaking_changes)


def test_field_removed_without_reuse_is_warning_only():
    old = "message M { string id = 1; string legacy_field = 2; }"
    new = "message M { string id = 1; }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes
    assert result.warnings


def test_cross_wire_type_change_is_breaking():
    old = "message M { string x = 1; }"
    new = "message M { int32 x = 1; }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes


def test_same_wire_group_type_change_is_warning_only():
    old = "message M { int32 x = 1; }"
    new = "message M { int64 x = 1; }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes
    assert result.warnings


def test_sint_crossing_standard_varint_is_breaking():
    old = "message M { sint32 x = 1; }"
    new = "message M { int32 x = 1; }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes


def test_sint32_to_sint64_is_not_breaking():
    old = "message M { sint32 x = 1; }"
    new = "message M { sint64 x = 1; }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes


def test_cardinality_change_is_breaking():
    old = "message M { string tags = 1; }"
    new = "message M { repeated string tags = 1; }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes


def test_enum_value_renamed_at_same_number_is_warning_only():
    old = "enum Role { ADMIN = 0; MEMBER = 1; }"
    new = "enum Role { ADMIN = 0; GUEST = 1; }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes
    assert result.warnings


def test_enum_value_removed_without_reuse_is_warning_only():
    old = "enum Role { ADMIN = 0; MEMBER = 1; GUEST = 2; }"
    new = "enum Role { ADMIN = 0; MEMBER = 1; }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes
    assert result.warnings


def test_removed_rpc_method_is_breaking():
    old = "service S { rpc Get(Req) returns (Res); rpc Delete(Req) returns (Res); }"
    new = "service S { rpc Get(Req) returns (Res); }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes


def test_new_rpc_method_is_info():
    old = "service S { rpc Get(Req) returns (Res); }"
    new = "service S { rpc Get(Req) returns (Res); rpc List(Req) returns (Res); }"
    result = diff_protos(old, new)
    assert not result.has_breaking_changes


def test_rpc_response_type_change_is_breaking():
    old = "service S { rpc Get(Req) returns (Res); }"
    new = "service S { rpc Get(Req) returns (OtherRes); }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes


def test_rpc_streaming_change_is_breaking():
    old = "service S { rpc Get(Req) returns (Res); }"
    new = "service S { rpc Get(Req) returns (stream Res); }"
    result = diff_protos(old, new)
    assert result.has_breaking_changes
