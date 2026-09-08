"""
A rule-based linter for a single OpenAPI/Swagger specification.

Unlike specshift's diff engines, this doesn't compare two versions; it
reviews one document for spec-validity problems (things that could break
tooling, code generators, or strict parsers) and common API design best
practices. It reuses the same Change/Severity/DiffResult models as the
diff engines, so every existing report format (console, Markdown, JSON,
HTML, SARIF) works on lint results without any changes.

Severity here maps onto the same three levels used elsewhere:
- breaking: the document violates something the OpenAPI specification
  itself requires (a missing required field, an invalid reference, a
  path parameter that isn't marked required), which can cause strict
  tooling, codegen, or validators to reject the document outright.
- warning: not invalid, but a common best-practice gap (missing
  descriptions, missing operationId, no documented error responses,
  inconsistent path naming).
- info: minor, low-priority suggestions (an apparently unused schema).

This is intentionally OpenAPI-focused for now; GraphQL and Protobuf
linting are not yet implemented.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Optional

from specshift.models import Change, ChangeType, DiffResult, Severity

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_SAFE_METHODS = {"get", "head", "options"}
_PATH_PARAM_RE = re.compile(r"^\{([^}]+)\}$")
_PATH_PARAM_NAMES_RE = re.compile(r"\{([^}]+)\}")
_SCHEMA_REF_RE = re.compile(r'#/components/schemas/([A-Za-z0-9_.\-]+)')


def lint_spec(spec: dict) -> DiffResult:
    """Lints a parsed OpenAPI/Swagger document and returns the findings as a DiffResult."""
    title = (spec.get("info", {}) or {}).get("title", "") or ""
    version = (spec.get("info", {}) or {}).get("version", "") or ""
    result = DiffResult(old_title=title, new_title=title, old_version=version, new_version=version)

    _lint_info(spec, result)
    _lint_paths(spec, result)
    _lint_security_schemes(spec, result)
    _lint_unused_schemas(spec, result)

    return result


def _lint_info(spec: dict, result: DiffResult) -> None:
    info = spec.get("info", {}) or {}
    if not info.get("description"):
        result.add(
            Change(
                severity=Severity.INFO,
                change_type=ChangeType.MODIFIED,
                location="info",
                message="API has no top-level description. Consider adding one so consumers understand its purpose.",
                category="lint_info",
            )
        )


def _detect_case_style(segment: str) -> Optional[str]:
    if "-" in segment and "_" not in segment:
        return "kebab-case"
    if "_" in segment and "-" not in segment:
        return "snake_case"
    if re.search(r"[a-z][A-Z]", segment):
        return "camelCase"
    return None


def _lint_path_naming(path: str, styles_counter: Counter) -> None:
    for segment in path.strip("/").split("/"):
        if not segment or _PATH_PARAM_RE.match(segment):
            continue
        style = _detect_case_style(segment)
        if style:
            styles_counter[style] += 1


def _collect_path_param_names(params: list) -> set:
    names = set()
    for param in params or []:
        if isinstance(param, dict) and param.get("in") == "path" and param.get("name"):
            names.add(param["name"])
    return names


def _lint_path_parameters(path: str, path_item: dict, result: DiffResult) -> None:
    template_params = set(_PATH_PARAM_NAMES_RE.findall(path))
    path_level_params = path_item.get("parameters", []) or []
    path_level_names = _collect_path_param_names(path_level_params)

    for param in path_level_params:
        if isinstance(param, dict) and param.get("in") == "path" and param.get("required") is not True:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=path,
                    message=(
                        f"Path parameter '{param.get('name')}' is declared at the path level without "
                        "'required: true'. The OpenAPI spec requires path parameters to always be required."
                    ),
                    category="lint_parameter",
                )
            )

    for method in HTTP_METHODS:
        if method not in path_item or not isinstance(path_item[method], dict):
            continue
        op = path_item[method]
        loc = f"{method.upper()} {path}"
        op_params = op.get("parameters", []) or []
        op_level_names = _collect_path_param_names(op_params)

        missing = template_params - (path_level_names | op_level_names)
        for name in sorted(missing):
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=loc,
                    message=(
                        f"Path template parameter '{{{name}}}' is used in the path but not declared as a "
                        "path parameter for this operation."
                    ),
                    category="lint_parameter",
                )
            )

        for param in op_params:
            if isinstance(param, dict) and param.get("in") == "path" and param.get("required") is not True:
                result.add(
                    Change(
                        severity=Severity.BREAKING,
                        change_type=ChangeType.MODIFIED,
                        location=loc,
                        message=(
                            f"Path parameter '{param.get('name')}' is declared without 'required: true'. "
                            "The OpenAPI spec requires path parameters to always be required."
                        ),
                        category="lint_parameter",
                    )
                )


def _lint_responses(loc: str, responses: dict) -> list:
    findings = []
    for status, response in (responses or {}).items():
        if not isinstance(response, dict):
            continue
        if "$ref" in response:
            continue  # resolving cross-file/registered component refs is out of scope for this check
        description = response.get("description")
        if not description or not str(description).strip():
            findings.append(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=f"{loc} > response {status}",
                    message="Response has no description. The OpenAPI spec requires every response to have one.",
                    category="lint_response",
                )
            )
    return findings


def _lint_paths(spec: dict, result: DiffResult) -> None:
    paths = spec.get("paths", {}) or {}
    operation_ids: Counter = Counter()
    path_segment_styles: Counter = Counter()

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        _lint_path_parameters(path, path_item, result)
        _lint_path_naming(path, path_segment_styles)

        for method in HTTP_METHODS:
            if method not in path_item or not isinstance(path_item[method], dict):
                continue
            op = path_item[method]
            loc = f"{method.upper()} {path}"

            if not op.get("summary") and not op.get("description"):
                result.add(
                    Change(
                        severity=Severity.WARNING,
                        change_type=ChangeType.MODIFIED,
                        location=loc,
                        message="Operation has no summary or description.",
                        category="lint_operation",
                    )
                )

            op_id = op.get("operationId")
            if not op_id:
                result.add(
                    Change(
                        severity=Severity.WARNING,
                        change_type=ChangeType.MODIFIED,
                        location=loc,
                        message="Operation has no operationId; many code generators rely on this to name functions.",
                        category="lint_operation",
                    )
                )
            else:
                operation_ids[op_id] += 1

            responses = op.get("responses", {}) or {}
            if method not in _SAFE_METHODS and not any(str(status).startswith(("4", "5")) for status in responses):
                result.add(
                    Change(
                        severity=Severity.WARNING,
                        change_type=ChangeType.MODIFIED,
                        location=loc,
                        message="No error response (4xx/5xx) is documented for this operation.",
                        category="lint_operation",
                    )
                )

            for finding in _lint_responses(loc, responses):
                result.add(finding)

    for op_id, count in operation_ids.items():
        if count > 1:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=f"operationId '{op_id}'",
                    message=(
                        f"operationId '{op_id}' is used {count} times; operationIds must be unique "
                        "across the whole document."
                    ),
                    category="lint_operation",
                )
            )

    if len(path_segment_styles) > 1:
        dominant_style, _ = path_segment_styles.most_common(1)[0]
        all_styles = ", ".join(sorted(path_segment_styles))
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.MODIFIED,
                location="paths",
                message=(
                    f"Path segments mix naming conventions ({all_styles}); most paths use {dominant_style}. "
                    "Consider using one convention consistently."
                ),
                category="lint_style",
            )
        )


def _lint_security_schemes(spec: dict, result: DiffResult) -> None:
    defined_schemes = set(((spec.get("components", {}) or {}).get("securitySchemes", {}) or {}).keys())

    def check(requirements, loc: str) -> None:
        for requirement in requirements or []:
            if not isinstance(requirement, dict):
                continue
            for scheme_name in requirement:
                if scheme_name not in defined_schemes:
                    result.add(
                        Change(
                            severity=Severity.BREAKING,
                            change_type=ChangeType.MODIFIED,
                            location=loc,
                            message=(
                                f"Security requirement references undefined scheme '{scheme_name}'. "
                                "Add it under components.securitySchemes."
                            ),
                            category="lint_security",
                        )
                    )

    check(spec.get("security"), "security (global)")

    for path, path_item in (spec.get("paths", {}) or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            if method not in path_item or not isinstance(path_item[method], dict):
                continue
            op = path_item[method]
            if "security" in op:
                check(op.get("security"), f"{method.upper()} {path}")


def _lint_unused_schemas(spec: dict, result: DiffResult) -> None:
    schemas = ((spec.get("components", {}) or {}).get("schemas", {}) or {})
    if not schemas:
        return

    try:
        serialized = json.dumps(spec)
    except (TypeError, ValueError):
        return

    referenced = set(_SCHEMA_REF_RE.findall(serialized))

    for name in schemas:
        if name not in referenced:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.MODIFIED,
                    location=f"components.schemas.{name}",
                    message=(
                        f"Schema '{name}' is defined but doesn't appear to be referenced anywhere in this "
                        "document. If it's unused, consider removing it."
                    ),
                    category="lint_unused",
                )
            )
