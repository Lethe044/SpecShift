"""
Compares two directories full of specification files (OpenAPI, GraphQL,
or Protobuf), matching files by relative path and diffing each pair.
Useful for monorepos or microservice architectures where many
independent contract files live side by side.

The result is a single aggregated DiffResult, so it renders through the
exact same reporters (console, Markdown, JSON, HTML, SARIF) as every
other command.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from specshift.differ import diff_specs
from specshift.engine_detect import detect_engine
from specshift.graphql_differ import diff_graphql
from specshift.models import Change, ChangeType, DiffResult, Severity
from specshift.protobuf_differ import diff_protos
from specshift.spec_loader import SpecLoadError, parse_spec_text

DEFAULT_PATTERNS = ("*.yaml", "*.yml", "*.json", "*.graphql", "*.gql", "*.proto")


def _diff_by_engine(engine: str, old_text: str, new_text: str) -> DiffResult:
    if engine == "graphql":
        return diff_graphql(old_text, new_text)
    if engine == "proto":
        return diff_protos(old_text, new_text)
    old_spec = parse_spec_text(old_text, hint="old")
    new_spec = parse_spec_text(new_text, hint="new")
    return diff_specs(old_spec, new_spec)


def _collect_files(root: Path, patterns) -> dict:
    files: dict = {}
    if not root.exists() or not root.is_dir():
        return files

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns):
            rel = path.relative_to(root)
            files[str(rel).replace("\\", "/")] = path

    return files


def _file_change(severity: Severity, change_type: ChangeType, rel_path: str, message: str) -> Change:
    return Change(
        severity=severity,
        change_type=change_type,
        location=rel_path,
        message=message,
        category="file",
    )


def diff_directories(old_dir: str, new_dir: str, patterns=DEFAULT_PATTERNS) -> DiffResult:
    """
    Compares every matching file in old_dir against its counterpart (by
    relative path) in new_dir. Files present in only one directory are
    reported as a whole-file addition or removal rather than diffed.
    """
    old_files = _collect_files(Path(old_dir), patterns)
    new_files = _collect_files(Path(new_dir), patterns)

    result = DiffResult(old_title=str(old_dir), new_title=str(new_dir))

    for rel_path in sorted(set(old_files) - set(new_files)):
        result.add(
            _file_change(
                Severity.BREAKING,
                ChangeType.REMOVED,
                rel_path,
                f"Specification file '{rel_path}' has been removed entirely.",
            )
        )

    for rel_path in sorted(set(new_files) - set(old_files)):
        result.add(
            _file_change(
                Severity.INFO,
                ChangeType.ADDED,
                rel_path,
                f"New specification file added: '{rel_path}'.",
            )
        )

    for rel_path in sorted(set(old_files) & set(new_files)):
        try:
            old_text = old_files[rel_path].read_text(encoding="utf-8")
            new_text = new_files[rel_path].read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.add(
                _file_change(
                    Severity.WARNING,
                    ChangeType.MODIFIED,
                    rel_path,
                    f"Could not read this file to compare it: {exc}",
                )
            )
            continue

        if old_text == new_text:
            continue

        try:
            sub_result = _diff_by_engine(detect_engine(rel_path), old_text, new_text)
        except SpecLoadError as exc:
            result.add(
                _file_change(
                    Severity.WARNING,
                    ChangeType.MODIFIED,
                    rel_path,
                    f"Could not parse this file to compare it: {exc}",
                )
            )
            continue

        for change in sub_result.changes:
            result.add(
                Change(
                    severity=change.severity,
                    change_type=change.change_type,
                    location=f"{rel_path} :: {change.location}",
                    message=change.message,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    category=change.category,
                )
            )

    return result
