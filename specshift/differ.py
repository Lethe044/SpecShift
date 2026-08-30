"""
Iki OpenAPI/Swagger spesifikasyonunu karsilastirip degisiklikleri
breaking, warning veya info olarak siniflandiran ana diff motoru.
"""

from __future__ import annotations

from typing import Any, Optional

from specshift.models import Change, ChangeType, DiffResult, Severity
from specshift.spec_loader import resolve_schema

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def diff_specs(old_spec: dict, new_spec: dict) -> DiffResult:
    """Iki spesifikasyonu karsilastirir ve DiffResult olarak doner."""
    result = DiffResult(
        old_title=_get_info(old_spec, "title"),
        new_title=_get_info(new_spec, "title"),
        old_version=_get_info(old_spec, "version"),
        new_version=_get_info(new_spec, "version"),
    )

    _diff_paths(old_spec, new_spec, result)
    _diff_servers(old_spec, new_spec, result)
    _diff_global_security(old_spec, new_spec, result)

    return result


def _get_info(spec: dict, key: str) -> str:
    return str(spec.get("info", {}).get(key, "")) if isinstance(spec, dict) else ""


def _diff_servers(old_spec: dict, new_spec: dict, result: DiffResult) -> None:
    old_servers = {s.get("url") for s in old_spec.get("servers", []) if isinstance(s, dict)}
    new_servers = {s.get("url") for s in new_spec.get("servers", []) if isinstance(s, dict)}

    removed = old_servers - new_servers
    added = new_servers - old_servers

    for url in removed:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.REMOVED,
                location="servers",
                message=f"Sunucu adresi kaldirilmis: {url}",
                old_value=url,
                category="server",
            )
        )
    for url in added:
        result.add(
            Change(
                severity=Severity.INFO,
                change_type=ChangeType.ADDED,
                location="servers",
                message=f"Yeni sunucu adresi eklenmis: {url}",
                new_value=url,
                category="server",
            )
        )


def _diff_global_security(old_spec: dict, new_spec: dict, result: DiffResult) -> None:
    old_sec = old_spec.get("security", [])
    new_sec = new_spec.get("security", [])

    if not old_sec and new_sec:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.ADDED,
                location="security (global)",
                message="API genelinde daha once zorunlu olmayan kimlik dogrulama artik zorunlu.",
                new_value=new_sec,
                category="security",
            )
        )
    elif old_sec and not new_sec:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.REMOVED,
                location="security (global)",
                message="API genelindeki zorunlu kimlik dogrulama kaldirilmis.",
                old_value=old_sec,
                category="security",
            )
        )


def _diff_paths(old_spec: dict, new_spec: dict, result: DiffResult) -> None:
    old_paths: dict = old_spec.get("paths", {}) or {}
    new_paths: dict = new_spec.get("paths", {}) or {}

    for path in old_paths:
        if path not in new_paths:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.REMOVED,
                    location=path,
                    message=f"Endpoint tamamen kaldirilmis: {path}",
                    category="path",
                )
            )

    for path in new_paths:
        if path not in old_paths:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=path,
                    message=f"Yeni endpoint eklenmis: {path}",
                    category="path",
                )
            )

    for path in old_paths:
        if path in new_paths:
            _diff_operations(path, old_paths[path], new_paths[path], old_spec, new_spec, result)


def _diff_operations(
    path: str,
    old_path_item: dict,
    new_path_item: dict,
    old_spec: dict,
    new_spec: dict,
    result: DiffResult,
) -> None:
    old_methods = {m for m in HTTP_METHODS if m in old_path_item}
    new_methods = {m for m in HTTP_METHODS if m in new_path_item}

    for method in old_methods - new_methods:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.REMOVED,
                location=f"{method.upper()} {path}",
                message=f"HTTP metodu kaldirilmis: {method.upper()} {path}",
                category="operation",
            )
        )

    for method in new_methods - old_methods:
        result.add(
            Change(
                severity=Severity.INFO,
                change_type=ChangeType.ADDED,
                location=f"{method.upper()} {path}",
                message=f"Yeni HTTP metodu eklenmis: {method.upper()} {path}",
                category="operation",
            )
        )

    for method in old_methods & new_methods:
        loc = f"{method.upper()} {path}"
        old_op = old_path_item[method]
        new_op = new_path_item[method]

        if bool(old_op.get("deprecated")) is False and bool(new_op.get("deprecated")) is True:
            result.add(
                Change(
                    severity=Severity.WARNING,
                    change_type=ChangeType.MODIFIED,
                    location=loc,
                    message="Operasyon deprecated (kullanimdan kaldirilacak) olarak isaretlenmis.",
                    category="operation",
                )
            )

        _diff_operation_security(loc, old_op, new_op, result)
        _diff_parameters(loc, old_op, new_op, old_spec, new_spec, result)
        _diff_request_body(loc, old_op, new_op, old_spec, new_spec, result)
        _diff_responses(loc, old_op, new_op, old_spec, new_spec, result)


def _diff_operation_security(loc: str, old_op: dict, new_op: dict, result: DiffResult) -> None:
    if "security" not in old_op and "security" not in new_op:
        return

    old_sec = old_op.get("security")
    new_sec = new_op.get("security")

    if not old_sec and new_sec:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.ADDED,
                location=loc,
                message="Bu operasyona yeni bir zorunlu kimlik dogrulama sarti eklenmis.",
                category="security",
            )
        )
    elif old_sec and new_sec == []:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.REMOVED,
                location=loc,
                message="Bu operasyon icin kimlik dogrulama sarti kaldirilmis.",
                category="security",
            )
        )


def _param_key(param: dict) -> tuple:
    return (param.get("name"), param.get("in"))


def _collect_params(op: dict, root_spec: dict) -> dict:
    params: dict = {}
    for raw in op.get("parameters", []) or []:
        resolved = resolve_schema(raw, root_spec) if "$ref" in raw else raw
        if isinstance(resolved, dict) and "name" in resolved:
            params[_param_key(resolved)] = resolved
    return params


def _diff_parameters(
    loc: str, old_op: dict, new_op: dict, old_spec: dict, new_spec: dict, result: DiffResult
) -> None:
    old_params = _collect_params(old_op, old_spec)
    new_params = _collect_params(new_op, new_spec)

    for key, param in old_params.items():
        name, location_in = key
        if key not in new_params:
            required = bool(param.get("required")) or location_in == "path"
            severity = Severity.BREAKING if required else Severity.WARNING
            result.add(
                Change(
                    severity=severity,
                    change_type=ChangeType.REMOVED,
                    location=loc,
                    message=f"'{name}' ({location_in}) parametresi kaldirilmis.",
                    category="parameter",
                )
            )

    for key, param in new_params.items():
        name, location_in = key
        if key not in old_params:
            required = bool(param.get("required")) or location_in == "path"
            severity = Severity.BREAKING if required else Severity.INFO
            message = (
                f"Yeni zorunlu parametre eklenmis: '{name}' ({location_in})."
                if required
                else f"Yeni istege bagli parametre eklenmis: '{name}' ({location_in})."
            )
            result.add(
                Change(
                    severity=severity,
                    change_type=ChangeType.ADDED,
                    location=loc,
                    message=message,
                    category="parameter",
                )
            )

    for key in set(old_params) & set(new_params):
        name, location_in = key
        old_param = old_params[key]
        new_param = new_params[key]
        param_loc = f"{loc} > parametre '{name}'"

        old_required = bool(old_param.get("required")) or location_in == "path"
        new_required = bool(new_param.get("required")) or location_in == "path"

        if not old_required and new_required:
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=param_loc,
                    message=f"'{name}' parametresi artik zorunlu.",
                    category="parameter",
                )
            )
        elif old_required and not new_required:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.MODIFIED,
                    location=param_loc,
                    message=f"'{name}' parametresi artik istege bagli.",
                    category="parameter",
                )
            )

        old_schema = old_param.get("schema", {})
        new_schema = new_param.get("schema", {})
        if old_schema or new_schema:
            _diff_schema(
                resolve_schema(old_schema, old_spec),
                resolve_schema(new_schema, new_spec),
                param_loc,
                old_spec,
                new_spec,
                result,
                context="request",
            )


def _get_json_schema(content: dict, root_spec: dict) -> Optional[dict]:
    if not content:
        return None
    media = content.get("application/json") or next(iter(content.values()), None)
    if not isinstance(media, dict):
        return None
    schema = media.get("schema")
    if not schema:
        return None
    return resolve_schema(schema, root_spec)


def _diff_request_body(
    loc: str, old_op: dict, new_op: dict, old_spec: dict, new_spec: dict, result: DiffResult
) -> None:
    old_body = old_op.get("requestBody")
    new_body = new_op.get("requestBody")

    if old_body and not new_body:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.REMOVED,
                location=loc,
                message="Request body tamamen kaldirilmis.",
                category="request_body",
            )
        )
        return

    if not old_body and new_body:
        required = bool(new_body.get("required"))
        result.add(
            Change(
                severity=Severity.BREAKING if required else Severity.INFO,
                change_type=ChangeType.ADDED,
                location=loc,
                message="Yeni bir request body eklenmis"
                + (" ve zorunlu kilinmis." if required else " (istege bagli)."),
                category="request_body",
            )
        )
        return

    if not old_body or not new_body:
        return

    old_required = bool(old_body.get("required"))
    new_required = bool(new_body.get("required"))
    if not old_required and new_required:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message="Request body artik zorunlu.",
                category="request_body",
            )
        )

    old_schema = _get_json_schema(old_body.get("content", {}), old_spec)
    new_schema = _get_json_schema(new_body.get("content", {}), new_spec)

    if old_schema is not None or new_schema is not None:
        _diff_schema(
            old_schema or {},
            new_schema or {},
            f"{loc} > request body",
            old_spec,
            new_spec,
            result,
            context="request",
        )


def _diff_responses(
    loc: str, old_op: dict, new_op: dict, old_spec: dict, new_spec: dict, result: DiffResult
) -> None:
    old_responses = old_op.get("responses", {}) or {}
    new_responses = new_op.get("responses", {}) or {}

    for status in old_responses:
        if status not in new_responses:
            is_success = status.startswith("2")
            result.add(
                Change(
                    severity=Severity.BREAKING if is_success else Severity.WARNING,
                    change_type=ChangeType.REMOVED,
                    location=loc,
                    message=f"'{status}' yaniti tanimindan kaldirilmis.",
                    category="response",
                )
            )

    for status in new_responses:
        if status not in old_responses:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.ADDED,
                    location=loc,
                    message=f"Yeni '{status}' yaniti eklenmis.",
                    category="response",
                )
            )

    for status in set(old_responses) & set(new_responses):
        resp_loc = f"{loc} > yanit {status}"
        old_schema = _get_json_schema(old_responses[status].get("content", {}), old_spec)
        new_schema = _get_json_schema(new_responses[status].get("content", {}), new_spec)

        if old_schema is not None or new_schema is not None:
            _diff_schema(
                old_schema or {},
                new_schema or {},
                resp_loc,
                old_spec,
                new_spec,
                result,
                context="response",
            )


def _merge_all_of(schema: dict, root_spec: dict, _depth: int = 0) -> dict:
    """allOf icindeki alt semalari tek bir semaya birlestirir (basit birlestirme)."""
    if _depth > 10 or "allOf" not in schema:
        return schema

    merged_properties: dict = dict(schema.get("properties", {}))
    merged_required: list = list(schema.get("required", []))
    merged_type = schema.get("type")

    for sub in schema.get("allOf", []):
        resolved_sub = resolve_schema(sub, root_spec)
        resolved_sub = _merge_all_of(resolved_sub, root_spec, _depth + 1)
        merged_properties.update(resolved_sub.get("properties", {}))
        merged_required.extend(resolved_sub.get("required", []))
        merged_type = merged_type or resolved_sub.get("type")

    result = dict(schema)
    result.pop("allOf", None)
    result["properties"] = merged_properties
    result["required"] = list(dict.fromkeys(merged_required))
    if merged_type:
        result["type"] = merged_type
    return result


def _diff_schema(
    old_schema: dict,
    new_schema: dict,
    loc: str,
    old_spec: dict,
    new_spec: dict,
    result: DiffResult,
    context: str,
    _depth: int = 0,
) -> None:
    if _depth > 12:
        return

    old_schema = resolve_schema(old_schema or {}, old_spec)
    new_schema = resolve_schema(new_schema or {}, new_spec)
    old_schema = _merge_all_of(old_schema, old_spec)
    new_schema = _merge_all_of(new_schema, new_spec)

    if not old_schema and not new_schema:
        return

    _diff_schema_type(old_schema, new_schema, loc, result)
    _diff_schema_enum(old_schema, new_schema, loc, result)
    _diff_schema_nullable(old_schema, new_schema, loc, context, result)

    old_type = old_schema.get("type")
    new_type = new_schema.get("type")

    if old_type == "array" or new_type == "array":
        old_items = resolve_schema(old_schema.get("items", {}), old_spec)
        new_items = resolve_schema(new_schema.get("items", {}), new_spec)
        if old_items or new_items:
            _diff_schema(
                old_items, new_items, f"{loc}[]", old_spec, new_spec, result, context, _depth + 1
            )
        return

    old_props = old_schema.get("properties", {}) or {}
    new_props = new_schema.get("properties", {}) or {}
    old_required = set(old_schema.get("required", []) or [])
    new_required = set(new_schema.get("required", []) or [])

    for name in old_props:
        if name not in new_props:
            field_loc = f"{loc} > alan '{name}'"
            if context == "response":
                result.add(
                    Change(
                        severity=Severity.BREAKING,
                        change_type=ChangeType.REMOVED,
                        location=field_loc,
                        message=f"'{name}' alani yanittan kaldirilmis, bu alana bagimli istemciler etkilenir.",
                        category="schema",
                    )
                )
            else:
                result.add(
                    Change(
                        severity=Severity.WARNING,
                        change_type=ChangeType.REMOVED,
                        location=field_loc,
                        message=f"'{name}' alani artik kabul edilmiyor (request semasindan kaldirilmis).",
                        category="schema",
                    )
                )

    for name in new_props:
        if name not in old_props:
            field_loc = f"{loc} > alan '{name}'"
            is_new_required = name in new_required
            if context == "request" and is_new_required:
                result.add(
                    Change(
                        severity=Severity.BREAKING,
                        change_type=ChangeType.ADDED,
                        location=field_loc,
                        message=f"Yeni zorunlu alan eklenmis: '{name}'. Mevcut istemciler bu alani gondermeli.",
                        category="schema",
                    )
                )
            else:
                result.add(
                    Change(
                        severity=Severity.INFO,
                        change_type=ChangeType.ADDED,
                        location=field_loc,
                        message=f"Yeni alan eklenmis: '{name}'.",
                        category="schema",
                    )
                )

    newly_required = (new_required - old_required) & set(old_props) & set(new_props)
    for name in newly_required:
        field_loc = f"{loc} > alan '{name}'"
        if context == "request":
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=field_loc,
                    message=f"'{name}' alani artik zorunlu.",
                    category="schema",
                )
            )
        else:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.MODIFIED,
                    location=field_loc,
                    message=f"'{name}' alani artik her zaman garanti ediliyor.",
                    category="schema",
                )
            )

    no_longer_required = (old_required - new_required) & set(old_props) & set(new_props)
    for name in no_longer_required:
        field_loc = f"{loc} > alan '{name}'"
        if context == "response":
            result.add(
                Change(
                    severity=Severity.BREAKING,
                    change_type=ChangeType.MODIFIED,
                    location=field_loc,
                    message=f"'{name}' alani artik garanti edilmiyor (opsiyonel oldu).",
                    category="schema",
                )
            )
        else:
            result.add(
                Change(
                    severity=Severity.INFO,
                    change_type=ChangeType.MODIFIED,
                    location=field_loc,
                    message=f"'{name}' alani artik istege bagli.",
                    category="schema",
                )
            )

    for name in set(old_props) & set(new_props):
        _diff_schema(
            old_props[name],
            new_props[name],
            f"{loc} > alan '{name}'",
            old_spec,
            new_spec,
            result,
            context,
            _depth + 1,
        )


def _diff_schema_type(old_schema: dict, new_schema: dict, loc: str, result: DiffResult) -> None:
    old_type = old_schema.get("type")
    new_type = new_schema.get("type")
    if old_type and new_type and old_type != new_type:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message=f"Veri tipi degisti: '{old_type}' -> '{new_type}'.",
                old_value=old_type,
                new_value=new_type,
                category="schema",
            )
        )
        return

    old_format = old_schema.get("format")
    new_format = new_schema.get("format")
    if old_format and new_format and old_format != new_format:
        result.add(
            Change(
                severity=Severity.WARNING,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message=f"Format degisti: '{old_format}' -> '{new_format}'.",
                old_value=old_format,
                new_value=new_format,
                category="schema",
            )
        )


def _diff_schema_enum(old_schema: dict, new_schema: dict, loc: str, result: DiffResult) -> None:
    old_enum = old_schema.get("enum")
    new_enum = new_schema.get("enum")
    if old_enum is None and new_enum is None:
        return

    old_set = set(old_enum or [])
    new_set = set(new_enum or [])

    removed_values = old_set - new_set
    added_values = new_set - old_set

    if old_enum is not None and new_enum is None:
        result.add(
            Change(
                severity=Severity.INFO,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message="Enum kisitlamasi tamamen kaldirilmis, artik her deger kabul ediliyor.",
                category="schema",
            )
        )
        return

    if removed_values:
        result.add(
            Change(
                severity=Severity.BREAKING,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message=f"Enum degerleri kaldirilmis: {sorted(str(v) for v in removed_values)}.",
                old_value=list(removed_values),
                category="schema",
            )
        )
    if added_values:
        result.add(
            Change(
                severity=Severity.INFO,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message=f"Yeni enum degerleri eklenmis: {sorted(str(v) for v in added_values)}.",
                new_value=list(added_values),
                category="schema",
            )
        )


def _diff_schema_nullable(
    old_schema: dict, new_schema: dict, loc: str, context: str, result: DiffResult
) -> None:
    old_nullable = bool(old_schema.get("nullable", False))
    new_nullable = bool(new_schema.get("nullable", False))

    if old_nullable == new_nullable:
        return

    if old_nullable and not new_nullable:
        severity = Severity.BREAKING if context == "response" else Severity.INFO
        result.add(
            Change(
                severity=severity,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message="Alan artik null kabul etmiyor.",
                category="schema",
            )
        )
    else:
        severity = Severity.INFO if context == "response" else Severity.WARNING
        result.add(
            Change(
                severity=severity,
                change_type=ChangeType.MODIFIED,
                location=loc,
                message="Alan artik null degeri kabul ediyor.",
                category="schema",
            )
        )
