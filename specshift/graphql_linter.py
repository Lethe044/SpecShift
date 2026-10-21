"""
A rule-based linter for a single GraphQL SDL schema.

Reviews one schema document (not a diff between two versions) for
structural issues and naming convention violations, following common
GraphQL conventions:

- Type names should be PascalCase.
- Field and argument names should be camelCase.
- Enum value names should be SCREAMING_SNAKE_CASE.
- A schema needs a `Query` root type to be servable at all.
- `@deprecated` should always include a `reason`, otherwise consumers
  have no idea what to migrate to.

Reuses the same Change/Severity/DiffResult models as the diff engines, so
every existing report format works on lint results without changes.
"""

from __future__ import annotations

import re

from specshift.graphql_differ import parse_sdl
from specshift.models import Change, ChangeType, DiffResult, Severity

_PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_CAMEL_CASE_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
_SCREAMING_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

_ROOT_OPERATION_TYPES = {"Query", "Mutation", "Subscription"}


def _finding(severity: Severity, location: str, message: str, category: str) -> Change:
    return Change(
        severity=severity,
        change_type=ChangeType.MODIFIED,
        location=location,
        message=message,
        category=category,
    )


def lint_graphql(text: str) -> DiffResult:
    """Lints a GraphQL SDL document and returns the findings as a DiffResult."""
    types = parse_sdl(text)
    result = DiffResult(old_title="GraphQL schema", new_title="GraphQL schema")

    _lint_root_types(types, result)
    _lint_naming(types, result)
    _lint_deprecations(types, result)
    _lint_unused_types(types, result)

    return result


def _lint_root_types(types: dict, result: DiffResult) -> None:
    if "Query" not in types:
        result.add(
            _finding(
                Severity.BREAKING,
                "schema",
                "No 'Query' type is defined. A valid, servable GraphQL schema must define a Query root type.",
                "lint_graphql_schema",
            )
        )


def _lint_naming(types: dict, result: DiffResult) -> None:
    for name, type_def in types.items():
        if type_def["kind"] != "scalar" and not _PASCAL_CASE_RE.match(name):
            result.add(
                _finding(
                    Severity.WARNING,
                    name,
                    f"Type name '{name}' is not PascalCase, which is the GraphQL naming convention.",
                    "lint_graphql_style",
                )
            )

        for field_name, field in type_def.get("fields", {}).items():
            if not _CAMEL_CASE_RE.match(field_name):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{name}.{field_name}",
                        f"Field name '{field_name}' is not camelCase, which is the GraphQL naming convention.",
                        "lint_graphql_style",
                    )
                )
            for arg_name in field.get("args", {}):
                if not _CAMEL_CASE_RE.match(arg_name):
                    result.add(
                        _finding(
                            Severity.WARNING,
                            f"{name}.{field_name}({arg_name})",
                            f"Argument name '{arg_name}' is not camelCase, which is the GraphQL naming convention.",
                            "lint_graphql_style",
                        )
                    )

        for value_name in type_def.get("enum_values", {}):
            if not _SCREAMING_SNAKE_RE.match(value_name):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{name}.{value_name}",
                        f"Enum value '{value_name}' is not SCREAMING_SNAKE_CASE, which is the GraphQL naming convention.",
                        "lint_graphql_style",
                    )
                )


def _lint_deprecations(types: dict, result: DiffResult) -> None:
    for name, type_def in types.items():
        for field_name, field in type_def.get("fields", {}).items():
            if field.get("deprecated") and not field.get("deprecated_has_reason"):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{name}.{field_name}",
                        'Field is marked @deprecated without a reason. Add @deprecated(reason: "...") '
                        "so consumers know what to use instead.",
                        "lint_graphql_deprecation",
                    )
                )

        for value_name, value in type_def.get("enum_values", {}).items():
            if value.get("deprecated") and not value.get("deprecated_has_reason"):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{name}.{value_name}",
                        'Enum value is marked @deprecated without a reason. Add @deprecated(reason: "...") '
                        "so consumers know what to use instead.",
                        "lint_graphql_deprecation",
                    )
                )


def _lint_unused_types(types: dict, result: DiffResult) -> None:
    referenced: set = set()

    for type_def in types.values():
        for field in type_def.get("fields", {}).values():
            referenced.add(field.get("base_name"))
            for arg in field.get("args", {}).values():
                referenced.add(arg.get("base_name"))
        referenced |= type_def.get("implements", set())
        referenced |= type_def.get("union_members", set())

    for name, type_def in types.items():
        if type_def["kind"] == "scalar" or name in _ROOT_OPERATION_TYPES:
            continue
        if name not in referenced:
            result.add(
                _finding(
                    Severity.INFO,
                    name,
                    f"Type '{name}' doesn't appear to be referenced by any field, argument, "
                    "interface, or union in this schema.",
                    "lint_graphql_unused",
                )
            )
