from specshift.graphql_differ import diff_graphql, parse_sdl


def test_parse_sdl_extracts_types_fields_and_enum_values():
    sdl = """
    type Query {
      user(id: ID!): User
    }

    type User {
      id: ID!
      name: String
    }

    enum Role {
      ADMIN
      MEMBER
    }
    """
    types = parse_sdl(sdl)
    assert set(types.keys()) == {"Query", "User", "Role"}
    assert "user" in types["Query"]["fields"]
    assert types["User"]["fields"]["id"]["nullable"] is False
    assert types["User"]["fields"]["name"]["nullable"] is True
    assert set(types["Role"]["enum_values"].keys()) == {"ADMIN", "MEMBER"}


def test_identical_schemas_produce_no_changes():
    sdl = "type User { id: ID! name: String }"
    result = diff_graphql(sdl, sdl)
    assert result.is_empty


def test_removed_type_is_breaking():
    old = "type User { id: ID! } type Legacy { id: ID! }"
    new = "type User { id: ID! }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes
    assert any(c.location == "Legacy" for c in result.breaking_changes)


def test_removed_output_field_is_breaking():
    old = "type User { id: ID! email: String }"
    new = "type User { id: ID! }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes
    assert any("User.email" in c.location for c in result.breaking_changes)


def test_removed_input_field_is_warning_only():
    old = "input CreateUserInput { name: String! nickname: String }"
    new = "input CreateUserInput { name: String! }"
    result = diff_graphql(old, new)
    assert not result.has_breaking_changes
    assert any(c.category == "graphql_field" for c in result.warnings)


def test_new_required_input_field_is_breaking():
    old = "input CreateUserInput { name: String! }"
    new = "input CreateUserInput { name: String! age: Int! }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes


def test_new_optional_output_field_is_info():
    old = "type User { id: ID! }"
    new = "type User { id: ID! bio: String }"
    result = diff_graphql(old, new)
    assert not result.has_breaking_changes


def test_output_field_becoming_nullable_is_breaking():
    old = "type User { id: ID! name: String! }"
    new = "type User { id: ID! name: String }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes


def test_input_field_becoming_non_null_is_breaking():
    old = "input CreateUserInput { name: String! email: String }"
    new = "input CreateUserInput { name: String! email: String! }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes


def test_enum_value_removed_is_breaking():
    old = "enum Role { ADMIN MEMBER GUEST }"
    new = "enum Role { ADMIN MEMBER }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes


def test_new_required_argument_is_breaking():
    old = "type Query { user(id: ID!): String }"
    new = "type Query { user(id: ID!, token: String!): String }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes


def test_new_optional_argument_is_not_breaking():
    old = "type Query { user(id: ID!): String }"
    new = "type Query { user(id: ID!, includeDeleted: Boolean): String }"
    result = diff_graphql(old, new)
    assert not result.has_breaking_changes


def test_field_type_change_is_breaking():
    old = "type User { age: Int }"
    new = "type User { age: String }"
    result = diff_graphql(old, new)
    assert result.has_breaking_changes


def test_deprecated_field_is_warning():
    old = "type User { legacyId: ID }"
    new = "type User { legacyId: ID @deprecated(reason: \"use id instead\") }"
    result = diff_graphql(old, new)
    assert not result.has_breaking_changes
    assert result.warnings
