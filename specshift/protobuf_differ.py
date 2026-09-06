"""
A lightweight, dependency-free .proto (Protocol Buffers) parser and diff
engine for proto2/proto3 IDL files.

Unlike the OpenAPI and GraphQL diff engines, protobuf compatibility is
governed by the binary wire format rather than by JSON shape, so the
severity rules here follow protobuf's own documented compatibility
guidance (see https://protobuf.dev/programming-guides/proto3/#updating):

- Adding a new field or rpc method is always safe (protobuf's wire format
  simply ignores fields it doesn't recognize), so additions are info-level
  even when nothing comparable would be safe in OpenAPI or GraphQL.
- A field's number, not its name, is what the wire format actually keys
  on. Changing a field's number is equivalent to removing one field and
  adding a different one, and is always breaking.
- Field types are compared by wire type category (varint, 64-bit,
  32-bit, length-delimited). Crossing categories corrupts data on the
  wire and is breaking. Changing type within the same category (e.g.
  int32 -> int64, or string -> bytes) is wire-compatible but can be lossy
  or change validation, so it is flagged as a warning. sint32/sint64 use
  zigzag encoding and are called out by the protobuf docs as incompatible
  with the other varint types despite sharing the same wire type tag, so
  that specific crossing is treated as breaking.
- Reusing a removed field's number for a differently-typed field is
  breaking, since old serialized bytes would be silently reinterpreted
  under the wrong wire type. Removing a field without reusing its number
  is only a warning (protobuf's own guidance recommends using `reserved`
  in this case, which this tool cannot fully verify from the file alone).
  Enum values carry no type information of their own (every enum value is
  just an integer on the wire), so renaming or reassigning an enum value's
  name is flagged as a warning rather than breaking: the bytes on the wire
  are unaffected, but generated code and application logic that branch on
  the symbolic name can behave differently.

This module intentionally covers the common, practical subset of the
language used by the vast majority of real-world .proto files: top-level
messages, enums, and services with unary or streaming rpc methods,
including fields declared inside `oneof` blocks. Deeply nested message
types, custom options, and extensions are outside the current scope.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import requests

from specshift.models import Change, ChangeType, DiffResult, Severity

_TOP_LEVEL_RE = re.compile(r"\b(message|enum|service)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{")

_FIELD_RE = re.compile(
    r"(?P<modifier>repeated|optional|required)?\s*"
    r"(?P<type>map<\s*[A-Za-z0-9_.]+\s*,\s*[A-Za-z0-9_.]+\s*>|[A-Za-z_][A-Za-z0-9_.]*)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<number>\d+)\s*(?:\[[^\]]*\])?\s*;"
)

_ENUM_VALUE_RE = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<number>-?\d+)\s*(?:\[[^\]]*\])?\s*;"
)

_RPC_RE = re.compile(
    r"rpc\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(?P<req_stream>stream\s+)?"
    r"(?P<request>[A-Za-z_][A-Za-z0-9_.]*)\s*\)\s*returns\s*\(\s*(?P<resp_stream>stream\s+)?"
    r"(?P<response>[A-Za-z_][A-Za-z0-9_.]*)\s*\)"
)

_SYNTAX_RE = re.compile(r'syntax\s*=\s*"([^"]+)"\s*;')

_VARINT_STANDARD = {"int32", "int64", "uint32", "uint64", "bool"}
_VARINT_ZIGZAG = {"sint32", "sint64"}
_WIRE_I64 = {"fixed64", "sfixed64", "double"}
_WIRE_I32 = {"fixed32", "sfixed32", "float"}
_WIRE_LEN = {"string", "bytes"}


class ProtoLoadError(Exception):
    """Raised when a .proto file cannot be loaded or parsed."""


def load_proto(source: str, timeout: int = 15) -> str:
    """Loads raw .proto text from a file path, an http(s) URL, or inline text."""
    source = source.strip()

    if re.match(r"^https?://", source, re.IGNORECASE):
        try:
            response = requests.get(timeout=timeout, url=source, headers={"Accept": "text/plain, */*"})
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ProtoLoadError(f"Could not fetch URL '{source}': {exc}") from exc
        return response.text

    path = Path(source)
    if path.exists() and path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProtoLoadError(f"Could not read file '{path}': {exc}") from exc

    if "message " in source or "syntax" in source or "service " in source:
        return source

    raise ProtoLoadError(
        f"Source not found or not recognized: '{source}'. "
        "Expected a file path, an http(s) URL, or raw .proto text."
    )


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _extract_top_level_blocks(text: str) -> list[tuple[str, str, str]]:
    """
    Finds top-level 'message', 'enum', and 'service' blocks using balanced
    brace matching, so nested constructs (like 'oneof' groups inside a
    message) don't truncate the block early.
    """
    blocks: list[tuple[str, str, str]] = []
    pos = 0

    while True:
        match = _TOP_LEVEL_RE.search(text, pos)
        if not match:
            break

        kind, name = match.group(1), match.group(2)
        brace_start = match.end() - 1
        depth = 0
        end = None
        i = brace_start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
            i += 1

        if end is None:
            break  # malformed input, stop parsing rather than looping forever

        blocks.append((kind, name, text[brace_start + 1 : end]))
        pos = end + 1

    return blocks


def parse_proto(text: str) -> dict:
    """Parses .proto text into a dict describing messages, enums, and services."""
    text = _strip_comments(text)

    syntax_match = _SYNTAX_RE.search(text)
    syntax = syntax_match.group(1) if syntax_match else "proto2"

    definitions: dict = {"syntax": syntax, "messages": {}, "enums": {}, "services": {}}

    for kind, name, body in _extract_top_level_blocks(text):
        if kind == "message":
            fields = {}
            for field_match in _FIELD_RE.finditer(body):
                fields[field_match.group("name")] = {
                    "modifier": field_match.group("modifier") or "singular",
                    "type": field_match.group("type"),
                    "number": int(field_match.group("number")),
                }
            definitions["messages"][name] = {"fields": fields}
        elif kind == "enum":
            values = {}
            for value_match in _ENUM_VALUE_RE.finditer(body):
                values[value_match.group("name")] = int(value_match.group("number"))
            definitions["enums"][name] = {"values": values}
        elif kind == "service":
            methods = {}
            for rpc_match in _RPC_RE.finditer(body):
                methods[rpc_match.group("name")] = {
                    "request": rpc_match.group("request"),
                    "request_streaming": bool(rpc_match.group("req_stream")),
                    "response": rpc_match.group("response"),
                    "response_streaming": bool(rpc_match.group("resp_stream")),
                }
            definitions["services"][name] = {"methods": methods}

    return definitions


def _wire_group(type_name: str, enum_names: set) -> str:
    if type_name in enum_names:
        return "varint"
    if type_name in _VARINT_STANDARD:
        return "varint"
    if type_name in _VARINT_ZIGZAG:
        return "varint_zigzag"
    if type_name in _WIRE_I64:
        return "i64"
    if type_name in _WIRE_I32:
        return "i32"
    if type_name in _WIRE_LEN:
        return "len"
    # map<...> and unrecognized identifiers (embedded message types, or
    # enum/message types defined in an imported file we can't see) are all
    # length-delimited on the wire, same as string/bytes/messages.
    return "len"


def diff_protos(old_text: str, new_text: str) -> DiffResult:
    """Compares two .proto documents and returns a DiffResult."""
    old_def = parse_proto(old_text)
    new_def = parse_proto(new_text)

    result = DiffResult(old_title="Protobuf schema", old_version=old_def["syntax"], new_version=new_def["syntax"])

    if old_def["syntax"] != new_def["syntax"]:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.MODIFIED,
                location="syntax",
                message=f"Proto syntax changed from '{old_def['syntax']}' to '{new_def['syntax']}'.",
                category="proto_syntax",
            )
        )

    enum_names = set(old_def["enums"]) | set(new_def["enums"])

    _diff_messages(old_def["messages"], new_def["messages"], enum_names, result)
    _diff_enums(old_def["enums"], new_def["enums"], result)
    _diff_services(old_def["services"], new_def["services"], result)

    return result


def _diff_messages(old_messages: dict, new_messages: dict, enum_names: set, result: DiffResult) -> None:
    for name in old_messages:
        if name not in new_messages:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=name,
                    message=f"Message '{name}' has been removed.",
                    category="proto_message",
                )
            )

    for name in new_messages:
        if name not in old_messages:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=name,
                    message=f"New message added: '{name}'.",
                    category="proto_message",
                )
            )

    for name in set(old_messages) & set(new_messages):
        _diff_fields(name, old_messages[name]["fields"], new_messages[name]["fields"], enum_names, result)


def _diff_fields(msg_name: str, old_fields: dict, new_fields: dict, enum_names: set, result: DiffResult) -> None:
    # A field whose name survives but whose number changes is always breaking,
    # regardless of what else changed, and is handled separately from the
    # number-keyed removal/addition logic below so it isn't mistaken for an
    # unrelated remove-and-add pair.
    renumbered_names = set()
    for name in set(old_fields) & set(new_fields):
        if old_fields[name]["number"] != new_fields[name]["number"]:
            renumbered_names.add(name)
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=f"{msg_name}.{name}",
                    message=(
                        f"Field '{name}' changed its field number from "
                        f"{old_fields[name]['number']} to {new_fields[name]['number']}; "
                        "field numbers must never change once published."
                    ),
                    category="proto_field",
                )
            )
            _diff_field_shape(msg_name, name, old_fields[name], new_fields[name], enum_names, result)

    old_numbers_to_skip = {old_fields[name]["number"] for name in renumbered_names}
    new_numbers_to_skip = {new_fields[name]["number"] for name in renumbered_names}

    old_by_number = {
        f["number"]: (name, f) for name, f in old_fields.items() if f["number"] not in old_numbers_to_skip
    }
    new_by_number = {
        f["number"]: (name, f) for name, f in new_fields.items() if f["number"] not in new_numbers_to_skip
    }

    for number, (old_name, old_field) in old_by_number.items():
        if number not in new_by_number:
            result.add(
                Change(
                    severity=Severity.WARNING,
                    change_type=ChangeType.REMOVED,
                    location=f"{msg_name}.{old_name}",
                    message=(
                        f"Field '{old_name}' (number {number}) has been removed. "
                        f"Consider adding 'reserved {number};' to prevent it from being reused."
                    ),
                    category="proto_field",
                )
            )
            continue

        new_name, new_field = new_by_number[number]

        if old_name != new_name:
            same_shape = old_field["type"] == new_field["type"] and old_field["modifier"] == new_field["modifier"]
            result.add(
                Change(
                    severity=Severity.WARNING,
                    change_type=ChangeType.MODIFIED,
                    location=f"{msg_name}.{new_name}",
                    message=(
                        f"Field number {number} was renamed from '{old_name}' to '{new_name}'"
                        + (
                            "; this is wire-safe but breaks any generated code referencing the old name."
                            if same_shape
                            else "."
                        )
                    ),
                    category="proto_field",
                )
            )
            _diff_field_cardinality(msg_name, new_name, old_field, new_field, result)
            # A type change alongside a name change at the same number is reported
            # below as a number-reuse issue instead, to avoid two overlapping
            # breaking messages describing the same underlying risk.
        else:
            _diff_field_shape(msg_name, new_name, old_field, new_field, enum_names, result)

    for number, (new_name, new_field) in new_by_number.items():
        if number not in old_by_number:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=f"{msg_name}.{new_name}",
                    message=f"New field added: '{new_name}' (number {number}). Adding fields is always wire-safe.",
                    category="proto_field",
                )
            )

    # A number that used to belong to one field and now belongs to a
    # differently-typed field is the dangerous case: old serialized bytes
    # would be silently reinterpreted under the new field's type.
    for number in set(old_by_number) & set(new_by_number):
        old_name, old_field = old_by_number[number]
        new_name, new_field = new_by_number[number]
        if old_name != new_name and old_field["type"] != new_field["type"]:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=f"{msg_name}.{new_name}",
                    message=(
                        f"Field number {number} previously held '{old_name}' ({old_field['type']}) and now holds "
                        f"'{new_name}' ({new_field['type']}); old serialized data will be misinterpreted."
                    ),
                    category="proto_field",
                )
            )


def _diff_field_cardinality(msg_name: str, field_name: str, old_field: dict, new_field: dict, result: DiffResult) -> None:
    field_loc = f"{msg_name}.{field_name}"
    old_repeated = old_field["modifier"] == "repeated"
    new_repeated = new_field["modifier"] == "repeated"
    if old_repeated != new_repeated:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=field_loc,
                message=(
                    f"Field '{field_name}' changed from {'repeated' if old_repeated else 'singular'} to "
                    f"{'repeated' if new_repeated else 'singular'}; this changes the wire representation."
                ),
                category="proto_field",
            )
        )


def _diff_field_shape(
    msg_name: str, field_name: str, old_field: dict, new_field: dict, enum_names: set, result: DiffResult
) -> None:
    field_loc = f"{msg_name}.{field_name}"

    _diff_field_cardinality(msg_name, field_name, old_field, new_field, result)

    old_type = old_field["type"]
    new_type = new_field["type"]
    if old_type == new_type:
        return

    old_group = _wire_group(old_type, enum_names)
    new_group = _wire_group(new_type, enum_names)

    zigzag_crossing = {old_group, new_group} == {"varint", "varint_zigzag"}

    if old_group != new_group or zigzag_crossing:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=field_loc,
                message=(
                    f"Field type changed from '{old_type}' to '{new_type}', which uses a different wire "
                    "representation; old serialized data will be corrupted or rejected."
                ),
                old_value=old_type,
                new_value=new_type,
                category="proto_field",
            )
        )
    else:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.MODIFIED,
                location=field_loc,
                message=(
                    f"Field type changed from '{old_type}' to '{new_type}'. This is wire-compatible, but the "
                    "value may be truncated, reinterpreted, or fail validation depending on the actual data."
                ),
                old_value=old_type,
                new_value=new_type,
                category="proto_field",
            )
        )


def _diff_enums(old_enums: dict, new_enums: dict, result: DiffResult) -> None:
    for name in old_enums:
        if name not in new_enums:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=name,
                    message=f"Enum '{name}' has been removed.",
                    category="proto_enum",
                )
            )

    for name in new_enums:
        if name not in old_enums:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=name,
                    message=f"New enum added: '{name}'.",
                    category="proto_enum",
                )
            )

    for name in set(old_enums) & set(new_enums):
        _diff_enum_values(name, old_enums[name]["values"], new_enums[name]["values"], result)


def _diff_enum_values(enum_name: str, old_values: dict, new_values: dict, result: DiffResult) -> None:
    old_by_number = {number: name for name, number in old_values.items()}
    new_by_number = {number: name for name, number in new_values.items()}

    for number, old_name in old_by_number.items():
        if number not in new_by_number:
            result.add(
                Change(
                    severity=Severity.WARNING,
                    change_type=ChangeType.REMOVED,
                    location=f"{enum_name}.{old_name}",
                    message=(
                        f"Enum value '{old_name}' (number {number}) has been removed. "
                        f"Consider adding 'reserved {number};' to prevent it from being reused."
                    ),
                    category="proto_enum_value",
                )
            )

    for number, new_name in new_by_number.items():
        if number not in old_by_number:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=f"{enum_name}.{new_name}",
                    message=f"New enum value added: '{new_name}' (number {number}).",
                    category="proto_enum_value",
                )
            )
        elif old_by_number[number] != new_name:
            result.add(
                Change(
                    severity=Severity.WARNING,
                    change_type=ChangeType.MODIFIED,
                    location=f"{enum_name}.{new_name}",
                    message=(
                        f"Enum value number {number} was renamed from '{old_by_number[number]}' to '{new_name}'; "
                        "wire-safe, but breaks generated code referencing the old name."
                    ),
                    category="proto_enum_value",
                )
            )


def _diff_services(old_services: dict, new_services: dict, result: DiffResult) -> None:
    for name in old_services:
        if name not in new_services:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=name,
                    message=f"Service '{name}' has been removed.",
                    category="proto_service",
                )
            )

    for name in new_services:
        if name not in old_services:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=name,
                    message=f"New service added: '{name}'.",
                    category="proto_service",
                )
            )

    for name in set(old_services) & set(new_services):
        _diff_rpc_methods(name, old_services[name]["methods"], new_services[name]["methods"], result)


def _diff_rpc_methods(service_name: str, old_methods: dict, new_methods: dict, result: DiffResult) -> None:
    for name in old_methods:
        if name not in new_methods:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=f"{service_name}.{name}",
                    message=f"RPC method '{name}' has been removed.",
                    category="proto_rpc",
                )
            )

    for name in new_methods:
        if name not in old_methods:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=f"{service_name}.{name}",
                    message=f"New RPC method added: '{name}'.",
                    category="proto_rpc",
                )
            )

    for name in set(old_methods) & set(new_methods):
        old_method = old_methods[name]
        new_method = new_methods[name]
        method_loc = f"{service_name}.{name}"

        if old_method["request"] != new_method["request"]:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=method_loc,
                    message=(
                        f"Request type changed from '{old_method['request']}' to '{new_method['request']}'."
                    ),
                    category="proto_rpc",
                )
            )
        if old_method["response"] != new_method["response"]:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=method_loc,
                    message=(
                        f"Response type changed from '{old_method['response']}' to '{new_method['response']}'."
                    ),
                    category="proto_rpc",
                )
            )
        if old_method["request_streaming"] != new_method["request_streaming"]:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=method_loc,
                    message="Request streaming mode changed, this changes the generated client/server signature.",
                    category="proto_rpc",
                )
            )
        if old_method["response_streaming"] != new_method["response_streaming"]:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=method_loc,
                    message="Response streaming mode changed, this changes the generated client/server signature.",
                    category="proto_rpc",
                )
            )
