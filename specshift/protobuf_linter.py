"""
A rule-based linter for a single Protobuf/gRPC .proto schema.

Reviews one schema document (not a diff between two versions), checking
rules verified against the official Protocol Buffers documentation
(https://protobuf.dev/programming-guides/proto3/):

- In proto3, the first value defined in an enum must be zero; the
  compiler rejects the file otherwise.
- Field numbers 19000 to 19999 are reserved for the Protocol Buffers
  implementation and must not be used.
- Message, enum, service and rpc names should be PascalCase; field names
  should be lower_snake_case; enum value names should be
  SCREAMING_SNAKE_CASE (per Google's protobuf style guide).
- A missing 'syntax' declaration silently defaults to proto2.
- A missing 'package' declaration risks name collisions.

Reuses the same Change/Severity/DiffResult models as the diff engines, so
every existing report format works on lint results without changes.
"""

from __future__ import annotations

import re

from specshift.models import Change, ChangeType, DiffResult, Severity
from specshift.protobuf_differ import parse_proto

_PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SCREAMING_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

_RESERVED_RANGE_START = 19000
_RESERVED_RANGE_END = 19999

_SYNTAX_DECL_RE = re.compile(r'syntax\s*=\s*"[^"]+"\s*;')
_PACKAGE_DECL_RE = re.compile(r"package\s+[A-Za-z0-9_.]+\s*;")


def _finding(severity: Severity, location: str, message: str, category: str) -> Change:
    return Change(
        severity=severity,
        change_type=ChangeType.MODIFIED,
        location=location,
        message=message,
        category=category,
    )


def lint_proto(text: str) -> DiffResult:
    """Lints a .proto document and returns the findings as a DiffResult."""
    definitions = parse_proto(text)
    result = DiffResult(old_title="Protobuf schema", new_title="Protobuf schema")

    _lint_declarations(text, result)
    _lint_messages(definitions, result)
    _lint_enums(definitions, result)
    _lint_services(definitions, result)

    return result


def _lint_declarations(text: str, result: DiffResult) -> None:
    if not _SYNTAX_DECL_RE.search(text):
        result.add(
            _finding(
                Severity.WARNING,
                "syntax",
                "No 'syntax' declaration found; this silently defaults to proto2. "
                "Add 'syntax = \"proto3\";' at the top of the file if that's not intended.",
                "lint_proto_declaration",
            )
        )

    if not _PACKAGE_DECL_RE.search(text):
        result.add(
            _finding(
                Severity.INFO,
                "package",
                "No 'package' declaration found. Adding one helps avoid name collisions when "
                "this schema is combined with others.",
                "lint_proto_declaration",
            )
        )


def _lint_messages(definitions: dict, result: DiffResult) -> None:
    for name, message in definitions.get("messages", {}).items():
        if not _PASCAL_CASE_RE.match(name):
            result.add(
                _finding(
                    Severity.WARNING,
                    name,
                    f"Message name '{name}' is not PascalCase, which is the standard protobuf style.",
                    "lint_proto_style",
                )
            )

        for field_name, field in message.get("fields", {}).items():
            if not _SNAKE_CASE_RE.match(field_name):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{name}.{field_name}",
                        f"Field name '{field_name}' is not lower_snake_case, which is the standard protobuf style.",
                        "lint_proto_style",
                    )
                )

            number = field["number"]
            if _RESERVED_RANGE_START <= number <= _RESERVED_RANGE_END:
                result.add(
                    _finding(
                        Severity.BREAKING,
                        f"{name}.{field_name}",
                        f"Field number {number} is in the range {_RESERVED_RANGE_START}-{_RESERVED_RANGE_END}, "
                        "which is reserved for the Protocol Buffers implementation and cannot be used.",
                        "lint_proto_field_number",
                    )
                )


def _lint_enums(definitions: dict, result: DiffResult) -> None:
    syntax = definitions.get("syntax", "proto2")

    for name, enum_def in definitions.get("enums", {}).items():
        if not _PASCAL_CASE_RE.match(name):
            result.add(
                _finding(
                    Severity.WARNING,
                    name,
                    f"Enum name '{name}' is not PascalCase, which is the standard protobuf style.",
                    "lint_proto_style",
                )
            )

        values = enum_def.get("values", {})
        for value_name in values:
            if not _SCREAMING_SNAKE_RE.match(value_name):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{name}.{value_name}",
                        f"Enum value '{value_name}' is not SCREAMING_SNAKE_CASE, which is the standard protobuf style.",
                        "lint_proto_style",
                    )
                )

        if syntax == "proto3" and values:
            first_name, first_number = next(iter(values.items()))
            if first_number != 0:
                result.add(
                    _finding(
                        Severity.BREAKING,
                        f"{name}.{first_name}",
                        f"The first value defined in a proto3 enum must be zero, but '{first_name}' is "
                        f"{first_number}. protoc will reject this file.",
                        "lint_proto_enum",
                    )
                )


def _lint_services(definitions: dict, result: DiffResult) -> None:
    for service_name, service in definitions.get("services", {}).items():
        if not _PASCAL_CASE_RE.match(service_name):
            result.add(
                _finding(
                    Severity.WARNING,
                    service_name,
                    f"Service name '{service_name}' is not PascalCase, which is the standard protobuf style.",
                    "lint_proto_style",
                )
            )

        for method_name in service.get("methods", {}):
            if not _PASCAL_CASE_RE.match(method_name):
                result.add(
                    _finding(
                        Severity.WARNING,
                        f"{service_name}.{method_name}",
                        f"RPC method name '{method_name}' is not PascalCase, which is the standard protobuf style.",
                        "lint_proto_style",
                    )
                )
