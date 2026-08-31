"""Renders a DiffResult into console, Markdown, and JSON reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from specshift.models import DiffResult, Severity

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    _HAS_RICH = True
except ImportError:  # fall back to plain text if rich is not installed
    _HAS_RICH = False

_SEVERITY_COLORS = {
    Severity.BREAKING: "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO: "cyan",
}


def print_console_report(result: DiffResult, verbose: bool = True) -> None:
    """Prints the result to the terminal with colors. Falls back to plain text without rich."""
    if _HAS_RICH:
        _print_rich_report(result, verbose=verbose)
    else:
        print(render_plain_text_report(result, verbose=verbose))


def _print_rich_report(result: DiffResult, verbose: bool) -> None:
    console = Console()
    counts = result.summary_counts()

    header = f"{result.old_title or 'Specification'} : {result.old_version} -> {result.new_version}"
    console.print(f"\n[bold]{header}[/bold]")
    console.print(
        f"[bold red]{counts['breaking']} breaking[/bold red], "
        f"[bold yellow]{counts['warning']} warning[/bold yellow], "
        f"[cyan]{counts['info']} info[/cyan] changes found.\n"
    )

    if result.is_empty:
        console.print("[green]No differences found between the two specifications.[/green]")
        return

    changes = result.sorted_changes() if verbose else result.breaking_changes + result.warnings

    table = Table(show_lines=False, expand=True)
    table.add_column("Severity", width=10)
    table.add_column("Location", ratio=1)
    table.add_column("Description", ratio=2)

    for change in changes:
        color = _SEVERITY_COLORS.get(change.severity, "white")
        table.add_row(
            Text(change.severity.value.upper(), style=color),
            change.location,
            change.message,
        )

    console.print(table)

    if result.has_breaking_changes:
        console.print(
            f"\n[bold red]Result: {counts['breaking']} breaking change(s) make this "
            "specification update risky for consumers.[/bold red]"
        )
    else:
        console.print("\n[bold green]Result: no breaking changes found.[/bold green]")


def render_plain_text_report(result: DiffResult, verbose: bool = True) -> str:
    lines: list[str] = []
    counts = result.summary_counts()

    lines.append(f"{result.old_title or 'Specification'} : {result.old_version} -> {result.new_version}")
    lines.append(
        f"{counts['breaking']} breaking, {counts['warning']} warning, {counts['info']} info changes found."
    )
    lines.append("")

    if result.is_empty:
        lines.append("No differences found between the two specifications.")
        return "\n".join(lines)

    changes = result.sorted_changes() if verbose else result.breaking_changes + result.warnings

    for change in changes:
        lines.append(f"{change.severity.icon} {change.location} :: {change.message}")

    lines.append("")
    if result.has_breaking_changes:
        lines.append(
            f"Result: {counts['breaking']} breaking change(s) make this update risky."
        )
    else:
        lines.append("Result: no breaking changes found.")

    return "\n".join(lines)


def render_markdown_report(result: DiffResult, ai_summary: str | None = None) -> str:
    counts = result.summary_counts()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"# API Contract Change Report")
    lines.append("")
    lines.append(f"**Source:** {result.old_title or 'API'} ({result.old_version} -> {result.new_version})")
    lines.append(f"**Generated at:** {timestamp}")
    lines.append("")

    if result.has_breaking_changes:
        lines.append(f"## Summary: {counts['breaking']} breaking change(s) found")
    else:
        lines.append("## Summary: no breaking changes found")

    lines.append("")
    lines.append(f"| Severity | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Breaking | {counts['breaking']} |")
    lines.append(f"| Warning | {counts['warning']} |")
    lines.append(f"| Info | {counts['info']} |")
    lines.append("")

    if ai_summary:
        lines.append("## AI Summary")
        lines.append("")
        lines.append(ai_summary)
        lines.append("")

    for severity, title in (
        (Severity.BREAKING, "Breaking Changes"),
        (Severity.WARNING, "Warnings"),
        (Severity.INFO, "Informational Changes"),
    ):
        changes = [c for c in result.sorted_changes() if c.severity == severity]
        if not changes:
            continue
        lines.append(f"## {title}")
        lines.append("")
        for change in changes:
            lines.append(f"- **{change.location}**: {change.message}")
        lines.append("")

    if result.is_empty:
        lines.append("No differences were found between the two specifications.")

    return "\n".join(lines)


def render_json_report(result: DiffResult, ai_summary: str | None = None) -> str:
    payload = {
        "old_title": result.old_title,
        "new_title": result.new_title,
        "old_version": result.old_version,
        "new_version": result.new_version,
        "summary": result.summary_counts(),
        "has_breaking_changes": result.has_breaking_changes,
        "ai_summary": ai_summary,
        "changes": [c.to_dict() for c in result.sorted_changes()],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
