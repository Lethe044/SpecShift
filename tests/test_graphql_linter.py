from specshift.graphql_linter import lint_graphql


def test_clean_schema_has_no_findings():
    schema = """
    type Query {
      user(id: ID!): User
    }

    type User {
      id: ID!
      fullName: String
      role: Role
    }

    enum Role {
      ADMIN
      MEMBER
    }
    """
    assert lint_graphql(schema).is_empty


def test_missing_query_type_is_breaking():
    result = lint_graphql("type User { id: ID! }")
    assert result.has_breaking_changes
    assert any("Query" in c.message for c in result.breaking_changes)


def test_non_pascal_case_type_is_warning():
    result = lint_graphql("type Query { x: String } type user { id: ID! }")
    assert any("PascalCase" in c.message and c.location == "user" for c in result.warnings)


def test_non_camel_case_field_is_warning():
    result = lint_graphql("type Query { x: String } type User { Full_Name: String }")
    assert any("camelCase" in c.message for c in result.warnings)


def test_non_camel_case_argument_is_warning():
    result = lint_graphql("type Query { user(User_Id: ID!): String }")
    assert any("Argument name" in c.message for c in result.warnings)


def test_non_screaming_snake_enum_value_is_warning():
    result = lint_graphql("type Query { x: String } enum Role { admin }")
    assert any("SCREAMING_SNAKE_CASE" in c.message for c in result.warnings)


def test_deprecated_without_reason_is_warning():
    result = lint_graphql("type Query { x: String } type User { legacyId: ID @deprecated }")
    assert any("without a reason" in c.message for c in result.warnings)


def test_deprecated_with_reason_is_not_flagged():
    result = lint_graphql('type Query { x: String } type User { legacyId: ID @deprecated(reason: "use id") }')
    assert not any("without a reason" in c.message for c in result.warnings)


def test_unused_type_is_info():
    result = lint_graphql("type Query { x: String } type Orphan { y: String }")
    assert any(c.location == "Orphan" for c in result.info_changes)


def test_type_referenced_via_field_is_not_unused():
    result = lint_graphql("type Query { user: User } type User { id: ID! }")
    assert not any(c.location == "User" and c.category == "lint_graphql_unused" for c in result.changes)
