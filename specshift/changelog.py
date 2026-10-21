"""
Walks a spec file's history across git tags and generates a single
Markdown changelog document summarizing what changed (and whether it was
breaking) between each consecutive release.

This turns specshift from a point-in-time diff tool into something that
can answer "what changed across all our releases", which is a common
maintenance task most API teams currently do by hand.
"""

from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from pathlib import Path

from specshift.differ import diff_specs
from specshift.engine_detect import detect_engine
from specshift.git_utils import (
    GitError,
    current_branch,
    file_exists_at_ref,
    list_tags_chronological,
    read_file_at_ref,
    tag_date,
)
from specshift.graphql_differ import diff_graphql
from specshift.models import DiffResult
from specshift.protobuf_differ import diff_protos
from specshift.spec_loader import SpecLoadError, parse_spec_text

class ChangelogError(Exception):
    """Raised when a changelog cannot be generated."""


def _detect_engine(spec_path: str) -> str:
    return detect_engine(spec_path)


def _diff_by_engine(engine: str, old_text: str, new_text: str) -> DiffResult:
    if engine == "graphql":
        return diff_graphql(old_text, new_text)
    if engine == "proto":
        return diff_protos(old_text, new_text)
    old_spec = parse_spec_text(old_text, hint="old")
    new_spec = parse_spec_text(new_text, hint="new")
    return diff_specs(old_spec, new_spec)


def relevant_tags(spec_path: str, pattern: str = "*", repo_path: str = ".") -> list[str]:
    """Returns, in chronological order, the tags where the given file exists and matches the pattern."""
    all_tags = list_tags_chronological(repo_path=repo_path)
    matching = [tag for tag in all_tags if fnmatch.fnmatch(tag, pattern)]
    return [tag for tag in matching if file_exists_at_ref(spec_path, tag, repo_path=repo_path)]


def build_changelog(
    spec_path: str,
    tags: list[str],
    repo_path: str = ".",
    include_working_tree: bool = True,
) -> str:
    """
    Builds a single Markdown changelog document by diffing the spec file
    across each consecutive pair of tags, and optionally a final section
    comparing the latest tag to the current working tree state.
    """
    engine = _detect_engine(spec_path)

    if len(tags) < 1 and not include_working_tree:
        raise ChangelogError(
            f"No tags contain '{spec_path}'. Nothing to compare. "
            "Try a different --tag-pattern, or pass --include-working to compare against the current file."
        )

    sections: list[str] = []
    transitions: list[tuple[str, str, str, str]] = []  # (old_label, new_label, old_text, new_text)

    for old_tag, new_tag in zip(tags, tags[1:]):
        try:
            old_text = read_file_at_ref(spec_path, old_tag, repo_path=repo_path)
            new_text = read_file_at_ref(spec_path, new_tag, repo_path=repo_path)
        except GitError as exc:
            raise ChangelogError(str(exc)) from exc
        transitions.append((old_tag, new_tag, old_text, new_text))

    if include_working_tree:
        current_path = Path(repo_path) / spec_path
        if current_path.exists():
            current_text = current_path.read_text(encoding="utf-8")
            baseline_tag = tags[-1] if tags else None
            if baseline_tag is not None:
                try:
                    baseline_text = read_file_at_ref(spec_path, baseline_tag, repo_path=repo_path)
                except GitError as exc:
                    raise ChangelogError(str(exc)) from exc
                if baseline_text.strip() != current_text.strip():
                    branch = current_branch(repo_path=repo_path)
                    transitions.append((baseline_tag, f"Unreleased ({branch})", baseline_text, current_text))

    if not transitions:
        raise ChangelogError(
            f"Found no version transitions to compare for '{spec_path}'. "
            "The file may not have changed across the available tags."
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        f"# API Changelog: {spec_path}",
        "",
        f"Generated {generated_at} from {len(transitions)} version transition(s).",
        "",
    ]

    for old_label, new_label, old_text, new_text in reversed(transitions):
        try:
            result = _diff_by_engine(engine, old_text, new_text)
        except SpecLoadError as exc:
            raise ChangelogError(f"Could not parse '{spec_path}' at '{old_label}' or '{new_label}': {exc}") from exc

        sections.append(_render_section(old_label, new_label, result, repo_path=repo_path))

    return "\n".join(header) + "\n" + "\n".join(sections)


def _render_section(old_label: str, new_label: str, result: DiffResult, repo_path: str) -> str:
    counts = result.summary_counts()
    date_str = tag_date(new_label, repo_path=repo_path) if not new_label.startswith("Unreleased") else ""
    date_suffix = f" ({date_str})" if date_str else ""

    lines = [f"## {old_label} -> {new_label}{date_suffix}", ""]

    if result.is_empty:
        lines.append("No changes detected in this file between these versions.")
        lines.append("")
        return "\n".join(lines)

    lines.append(
        f"**{counts['breaking']} breaking, {counts['warning']} warning, {counts['info']} info** change(s)."
    )
    lines.append("")

    for severity_label, changes in (
        ("Breaking", result.breaking_changes),
        ("Warnings", result.warnings),
        ("Additions & other changes", result.info_changes),
    ):
        if not changes:
            continue
        lines.append(f"**{severity_label}:**")
        lines.append("")
        for change in changes:
            lines.append(f"- `{change.location}`: {change.message}")
        lines.append("")

    return "\n".join(lines)
