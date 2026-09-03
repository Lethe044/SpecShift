"""
A lightweight GraphQL SDL (Schema Definition Language) parser and diff engine.

This module intentionally avoids depending on a full GraphQL library so that
specshift keeps a small, dependency-light footprint. It handles the common,
practical subset of SDL used by the vast majority of real-world schemas:
object types, input types, interfaces, enums, unions, scalars, field
arguments, non-null (!) and list ([...]) type wrappers, default values, and
the @deprecated directive.

The result is a DiffResult from specshift.models, so it can be rendered with
exactly the same console/Markdown/JSON reporters used for OpenAPI diffs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import requests

from specshift.models import Change, ChangeType, DiffResult, Severity

INPUT_LIKE_KINDS = {"input"}
OUTPUT_LIKE_KINDS = {"type", "interface"}

_TYPE_BLOCK_RE = re.compile(
    r"(?P<kind>type|input|interface|enum|union|scalar)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+implements\s+(?P<implements>[A-Za-z0-9_&\s]+))?"
    r"(?:\s*=\s*(?P<union_members>[A-Za-z0-9_\s|]+))?"
    r"(?:\s*\{(?P<body>[^}]*)\})?",
    re.MULTILINE,
)

_FIELD_LINE_RE = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\((?P<args>[^)]*)\))?"
    r"\s*:\s*(?P<type>[\[\]A-Za-z0-9_!]+)"
    r"(?:\s*=\s*(?P<default>[^@\s][^@]*?))?"
    r"(?P<directives>(?:\s*@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?)*)"
    r"(?=\s|$)"
)

_ENUM_VALUE_RE = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<directives>(?:\s*@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?)*)"
)


class GraphQLLoadError(Exception):
    """Raised when a GraphQL SDL document cannot be loaded or parsed."""


def load_sdl(source: str, timeout: int = 15) -> str:
    """Loads raw GraphQL SDL text from a file path, an http(s) URL, or inline text."""
    source = source.strip()

    if re.match(r"^https?://", source, re.IGNORECASE):
        try:
            response = requests.get(timeout=timeout, url=source, headers={"Accept": "text/plain, */*"})
            response.raise_for_status()
        except requests.RequestException as exc:
            raise GraphQLLoadError(f"Could not fetch URL '{source}': {exc}") from exc
        return response.text

    path = Path(source)
    if path.exists() and path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GraphQLLoadError(f"Could not read file '{path}': {exc}") from exc

    if "type " in source or "input " in source or "enum " in source:
        return source

    raise GraphQLLoadError(
        f"Source not found or not recognized: '{source}'. "
        "Expected a file path, an http(s) URL, or raw GraphQL SDL text."
    )


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "#" in line:
            line = line[: line.index("#")]
        lines.append(line)
    return "\n".join(lines)


def _parse_type_ref(raw: str) -> dict:
    """Parses a GraphQL type reference like '[String!]!' into a normalized form."""
    cleaned = raw.strip()
    is_list = cleaned.startswith("[")
    outer_non_null = cleaned.endswith("!")
    base = cleaned
    if base.endswith("!"):
        base = base[:-1]
    if base.startswith("[") and base.endswith("]"):
        base = base[1:-1]
    base_name = re.sub(r"[\[\]!]", "", base).strip()

    return {
        "raw": cleaned,
        "nullable": not outer_non_null,
        "is_list": is_list,
        "base_name": base_name,
    }


def _parse_args(args_text: Optional[str]) -> dict:
    args: dict = {}
    if not args_text or not args_text.strip():
        return args

    depth = 0
    current = []
    parts = []
    for ch in args_text:
        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))

    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.match(
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>[\[\]A-Za-z0-9_!\s]+?)"
            r"(?:\s*=\s*(?P<default>.+))?$",
            part,
        )
        if not match:
            continue
        type_ref = _parse_type_ref(match.group("type"))
        args[match.group("name")] = {
            **type_ref,
            "has_default": match.group("default") is not None,
            "default": match.group("default").strip() if match.group("default") else None,
        }

    return args


def parse_sdl(text: str) -> dict:
    """Parses GraphQL SDL text into a dict of type definitions keyed by type name."""
    text = _strip_comments(text)
    types: dict = {}

    for match in _TYPE_BLOCK_RE.finditer(text):
        kind = match.group("kind")
        name = match.group("name")
        body = match.group("body") or ""

        type_def = {
            "kind": kind,
            "fields": {},
            "enum_values": {},
            "implements": set(),
            "union_members": set(),
        }

        if match.group("implements"):
            type_def["implements"] = {
                part.strip() for part in re.split(r"[&\s]+", match.group("implements")) if part.strip()
            }

        if match.group("union_members"):
            type_def["union_members"] = {
                part.strip() for part in match.group("union_members").split("|") if part.strip()
            }

        if kind == "enum":
            for enum_match in _ENUM_VALUE_RE.finditer(body):
                value_name = enum_match.group("name")
                if not value_name:
                    continue
                deprecated = "@deprecated" in (enum_match.group("directives") or "")
                type_def["enum_values"][value_name] = {"deprecated": deprecated}
        elif kind in ("type", "input", "interface"):
            for field_match in _FIELD_LINE_RE.finditer(body):
                type_ref = _parse_type_ref(field_match.group("type"))
                deprecated = "@deprecated" in (field_match.group("directives") or "")
                type_def["fields"][field_match.group("name")] = {
                    **type_ref,
                    "args": _parse_args(field_match.group("args")),
                    "has_default": field_match.group("default") is not None,
                    "default": field_match.group("default").strip() if field_match.group("default") else None,
                    "deprecated": deprecated,
                }

        types[name] = type_def

    return types


def _context_for_kind(kind: str) -> str:
    return "request" if kind in INPUT_LIKE_KINDS else "response"


def diff_graphql(old_text: str, new_text: str) -> DiffResult:
    """Compares two GraphQL SDL documents and returns a DiffResult."""
    old_types = parse_sdl(old_text)
    new_types = parse_sdl(new_text)

    result = DiffResult(old_title="GraphQL schema", new_title="GraphQL schema")

    for name in old_types:
        if name not in new_types:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=name,
                    message=f"Type '{name}' has been removed from the schema.",
                    category="graphql_type",
                )
            )

    for name in new_types:
        if name not in old_types:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=name,
                    message=f"New type added: '{name}'.",
                    category="graphql_type",
                )
            )

    for name in set(old_types) & set(new_types):
        _diff_type(name, old_types[name], new_types[name], result)

    return result


def _diff_type(name: str, old_def: dict, new_def: dict, result: DiffResult) -> None:
    if old_def["kind"] != new_def["kind"]:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=name,
                message=f"Type kind changed from '{old_def['kind']}' to '{new_def['kind']}'.",
                category="graphql_type",
            )
        )
        return

    kind = new_def["kind"]

    if kind == "enum":
        _diff_enum_values(name, old_def["enum_values"], new_def["enum_values"], result)
        return

    if kind == "union":
        _diff_union_members(name, old_def["union_members"], new_def["union_members"], result)
        return

    if kind == "scalar":
        return

    removed_interfaces = old_def["implements"] - new_def["implements"]
    added_interfaces = new_def["implements"] - old_def["implements"]
    for iface in removed_interfaces:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.REMOVED,
                location=name,
                message=f"'{name}' no longer implements interface '{iface}'.",
                category="graphql_type",
            )
        )
    for iface in added_interfaces:
        result.add(
            Change(
                severity=Severity.INFO,
                change_type=ChangeType.ADDED,
                location=name,
                message=f"'{name}' now implements interface '{iface}'.",
                category="graphql_type",
            )
        )

    context = _context_for_kind(kind)
    _diff_fields(name, old_def["fields"], new_def["fields"], context, result)


def _diff_enum_values(name: str, old_values: dict, new_values: dict, result: DiffResult) -> None:
    for value in old_values:
        if value not in new_values:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=f"{name}.{value}",
                    message=f"Enum value '{value}' has been removed from '{name}'.",
                    category="graphql_enum",
                )
            )

    for value in new_values:
        if value not in old_values:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=f"{name}.{value}",
                    message=f"New enum value added to '{name}': '{value}'.",
                    category="graphql_enum",
                )
            )

    for value in set(old_values) & set(new_values):
        old_deprecated = old_values[value].get("deprecated", False)
        new_deprecated = new_values[value].get("deprecated", False)
        if not old_deprecated and new_deprecated:
            result.add(
                Change(
                    severity=Severity.WARNING,
                    change_type=ChangeType.MODIFIED,
                    location=f"{name}.{value}",
                    message=f"Enum value '{value}' has been marked as deprecated.",
                    category="graphql_enum",
                )
            )


def _diff_union_members(name: str, old_members: set, new_members: set, result: DiffResult) -> None:
    for member in old_members - new_members:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.REMOVED,
                location=name,
                message=f"'{member}' is no longer a member of union '{name}'.",
                category="graphql_union",
            )
        )
    for member in new_members - old_members:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.ADDED,
                location=name,
                message=f"'{member}' has been added as a member of union '{name}'; "
                "consumers switching on this union should handle the new case.",
                category="graphql_union",
            )
        )


def _diff_fields(type_name: str, old_fields: dict, new_fields: dict, context: str, result: DiffResult) -> None:
    for field_name in old_fields:
        if field_name not in new_fields:
            field_loc = f"{type_name}.{field_name}"
            if context == "request":
                result.add(
                    Change(
                        severity=Severity.WARNING,
                        change_type=ChangeType.REMOVED,
                        location=field_loc,
                        message=f"Input field '{field_name}' has been removed, values sent for it will be ignored.",
                        category="graphql_field",
                    )
                )
            else:
                result.add(
                    Change(
                        severity=Severity.BREAKING,
                        change_type=ChangeType.REMOVED,
                        location=field_loc,
                        message=f"Field '{field_name}' has been removed, existing queries selecting it will fail.",
                        category="graphql_field",
                    )
                )

    for field_name, field in new_fields.items():
        if field_name not in old_fields:
            field_loc = f"{type_name}.{field_name}"
            if context == "request" and not field["nullable"] and not field.get("has_default"):
                result.add(
                    Change(
                        severity=Severity.BREAKING,
                        change_type=ChangeType.ADDED,
                        location=field_loc,
                        message=f"New required input field added: '{field_name}'. Existing requests must now include it.",
                        category="graphql_field",
                    )
                )
            else:
                result.add(
                    Change(
                        severity=Severity.INFO,
                        change_type=ChangeType.ADDED,
                        location=field_loc,
                        message=f"New field added: '{field_name}'.",
                        category="graphql_field",
                    )
                )

    for field_name in set(old_fields) & set(new_fields):
        _diff_field(type_name, field_name, old_fields[field_name], new_fields[field_name], context, result)


def _diff_field(
    type_name: str, field_name: str, old_field: dict, new_field: dict, context: str, result: DiffResult
) -> None:
    field_loc = f"{type_name}.{field_name}"

    if old_field["base_name"] != new_field["base_name"] or old_field["is_list"] != new_field["is_list"]:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=field_loc,
                message=f"Field type changed from '{old_field['raw']}' to '{new_field['raw']}'.",
                old_value=old_field["raw"],
                new_value=new_field["raw"],
                category="graphql_field",
            )
        )
    elif old_field["nullable"] != new_field["nullable"]:
        became_non_null = old_field["nullable"] and not new_field["nullable"]
        if became_non_null:
            severity = Severity.BREAKING if context == "request" else Severity.INFO
            message = f"Field '{field_name}' is now non-null (was nullable)."
        else:
            severity = Severity.INFO if context == "request" else Severity.BREAKING
            message = f"Field '{field_name}' is now nullable (was non-null)."
        result.add(
            Change(
                severity=severity,
                change_type=ChangeType.MODIFIED,
                location=field_loc,
                message=message,
                category="graphql_field",
            )
        )

    if not old_field.get("deprecated") and new_field.get("deprecated"):
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.MODIFIED,
                location=field_loc,
                message=f"Field '{field_name}' has been marked as deprecated.",
                category="graphql_field",
            )
        )

    _diff_args(field_loc, old_field.get("args", {}), new_field.get("args", {}), result)


def _diff_args(field_loc: str, old_args: dict, new_args: dict, result: DiffResult) -> None:
    for arg_name in old_args:
        if arg_name not in new_args:
            required = not old_args[arg_name]["nullable"] and not old_args[arg_name].get("has_default")
            result.add(
                Change(
                    severity=Severity.BREAKING if required else Severity.WARNING,
                    change_type=ChangeType.REMOVED,
                    location=f"{field_loc}({arg_name})",
                    message=f"Argument '{arg_name}' has been removed.",
                    category="graphql_argument",
                )
            )

    for arg_name, arg in new_args.items():
        if arg_name not in old_args:
            required = not arg["nullable"] and not arg.get("has_default")
            result.add(
                Change(
                    severity=Severity.BREAKING if required else Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=f"{field_loc}({arg_name})",
                    message=(
                        f"New required argument added: '{arg_name}'."
                        if required
                        else f"New optional argument added: '{arg_name}'."
                    ),
                    category="graphql_argument",
                )
            )

    for arg_name in set(old_args) & set(new_args):
        old_arg = old_args[arg_name]
        new_arg = new_args[arg_name]
        arg_loc = f"{field_loc}({arg_name})"

        if old_arg["base_name"] != new_arg["base_name"] or old_arg["is_list"] != new_arg["is_list"]:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=arg_loc,
                    message=f"Argument type changed from '{old_arg['raw']}' to '{new_arg['raw']}'.",
                    category="graphql_argument",
                )
            )
        elif old_arg["nullable"] != new_arg["nullable"]:
            became_non_null = old_arg["nullable"] and not new_arg["nullable"]
            result.add(
                Change(
                    severity=Severity.BREAKING if became_non_null else Severity.INFO,
                    change_type=ChangeType.MODIFIED,
                    location=arg_loc,
                    message=(
                        f"Argument '{arg_name}' is now required."
                        if became_non_null
                        else f"Argument '{arg_name}' is now optional."
                    ),
                    category="graphql_argument",
                )
            )
