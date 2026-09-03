"""Renders a DiffResult into console, Markdown, JSON, and HTML reports."""

from __future__ import annotations

import html as html_module
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


def _format_header(result: DiffResult) -> str:
    title = result.old_title or "Specification"
    if result.old_version or result.new_version:
        return f"{title} : {result.old_version} -> {result.new_version}"
    return title


def print_console_report(result: DiffResult, verbose: bool = True) -> None:
    """Prints the result to the terminal with colors. Falls back to plain text without rich."""
    if _HAS_RICH:
        _print_rich_report(result, verbose=verbose)
    else:
        print(render_plain_text_report(result, verbose=verbose))


def _print_rich_report(result: DiffResult, verbose: bool) -> None:
    console = Console()
    counts = result.summary_counts()

    console.print(f"\n[bold]{_format_header(result)}[/bold]")
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

    lines.append(_format_header(result))
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
    lines.append(f"**Source:** {_format_header(result)}")
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


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --bg: #0d1117;
    --panel: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --muted: #8b949e;
    --breaking: #f85149;
    --warning: #d29922;
    --info: #58a6ff;
    --ok: #3fb950;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 2rem;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: var(--muted); margin-bottom: 1.5rem; }}
  .summary {{ display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .badge {{
    padding: 0.5rem 1rem;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--panel);
    font-weight: 600;
    cursor: pointer;
    user-select: none;
  }}
  .badge.active {{ outline: 2px solid var(--text); }}
  .badge.breaking {{ color: var(--breaking); }}
  .badge.warning {{ color: var(--warning); }}
  .badge.info {{ color: var(--info); }}
  .badge.all {{ color: var(--text); }}
  .toolbar {{ display: flex; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap; align-items: center; }}
  input[type="search"] {{
    flex: 1;
    min-width: 200px;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--panel);
    color: var(--text);
    font-size: 0.95rem;
  }}
  .ai-summary {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
    line-height: 1.5;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
  th {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  tr:hover {{ background: rgba(255,255,255,0.03); }}
  .sev {{ font-weight: 700; white-space: nowrap; }}
  .sev.breaking {{ color: var(--breaking); }}
  .sev.warning {{ color: var(--warning); }}
  .sev.info {{ color: var(--info); }}
  .location {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.85rem; color: var(--muted); }}
  .empty-state {{ text-align: center; padding: 3rem 1rem; color: var(--muted); }}
  .result-line {{ margin-top: 1.5rem; padding: 1rem; border-radius: 8px; border: 1px solid var(--border); }}
  .result-line.breaking {{ background: rgba(248,81,73,0.08); }}
  .result-line.ok {{ background: rgba(63,185,80,0.08); }}
  footer {{ margin-top: 2rem; color: var(--muted); font-size: 0.8rem; text-align: center; }}
  footer a {{ color: var(--info); }}
</style>
</head>
<body>
<div class="container">
  <h1>{title}</h1>
  <div class="subtitle">{subtitle_line}generated {timestamp}</div>

  <div class="summary">
    <div class="badge all active" data-filter="all">All ({total})</div>
    <div class="badge breaking" data-filter="breaking">Breaking ({breaking})</div>
    <div class="badge warning" data-filter="warning">Warning ({warning})</div>
    <div class="badge info" data-filter="info">Info ({info})</div>
  </div>

  {ai_summary_block}

  <div class="toolbar">
    <input type="search" id="search" placeholder="Filter by location or description...">
  </div>

  <table id="changes-table">
    <thead>
      <tr><th style="width:110px">Severity</th><th style="width:320px">Location</th><th>Description</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <div id="empty-state" class="empty-state" style="display:none;">No changes match the current filter.</div>

  <div class="result-line {result_class}">{result_text}</div>

  <footer>Generated by <a href="https://github.com/Lethe044/specshift" target="_blank" rel="noopener">specshift</a></footer>
</div>
<script>
  const badges = document.querySelectorAll('.badge');
  const rows = document.querySelectorAll('#changes-table tbody tr');
  const searchInput = document.getElementById('search');
  const emptyState = document.getElementById('empty-state');
  let currentFilter = 'all';

  function applyFilters() {{
    const query = searchInput.value.trim().toLowerCase();
    let visibleCount = 0;
    rows.forEach(row => {{
      const matchesSeverity = currentFilter === 'all' || row.dataset.severity === currentFilter;
      const matchesQuery = !query || row.dataset.search.includes(query);
      const visible = matchesSeverity && matchesQuery;
      row.style.display = visible ? '' : 'none';
      if (visible) visibleCount += 1;
    }});
    emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
  }}

  badges.forEach(badge => {{
    badge.addEventListener('click', () => {{
      badges.forEach(b => b.classList.remove('active'));
      badge.classList.add('active');
      currentFilter = badge.dataset.filter;
      applyFilters();
    }});
  }});

  searchInput.addEventListener('input', applyFilters);
</script>
</body>
</html>
"""


def render_html_report(result: DiffResult, ai_summary: str | None = None) -> str:
    """Renders a standalone, self-contained HTML report with client-side filtering."""
    counts = result.summary_counts()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    title = html_module.escape(result.old_title or "API Contract Change Report")
    subtitle_text = f"{result.old_version} -> {result.new_version}" if (result.old_version or result.new_version) else ""
    subtitle_line = f"{html_module.escape(subtitle_text)} &middot; " if subtitle_text else ""

    ai_block = ""
    if ai_summary:
        ai_block = f'<div class="ai-summary">{html_module.escape(ai_summary)}</div>'

    row_html = []
    for change in result.sorted_changes():
        severity = change.severity.value
        search_blob = html_module.escape(f"{change.location} {change.message}".lower())
        row_html.append(
            f'<tr data-severity="{severity}" data-search="{search_blob}">'
            f'<td class="sev {severity}">{severity.upper()}</td>'
            f'<td class="location">{html_module.escape(change.location)}</td>'
            f'<td>{html_module.escape(change.message)}</td>'
            f"</tr>"
        )

    if result.has_breaking_changes:
        result_class = "breaking"
        result_text = f"{counts['breaking']} breaking change(s) make this update risky for consumers."
    else:
        result_class = "ok"
        result_text = "No breaking changes found."

    return _HTML_TEMPLATE.format(
        title=title,
        subtitle_line=subtitle_line,
        timestamp=timestamp,
        total=counts["total"],
        breaking=counts["breaking"],
        warning=counts["warning"],
        info=counts["info"],
        ai_summary_block=ai_block,
        rows="\n      ".join(row_html) if row_html else "",
        result_class=result_class,
        result_text=result_text,
    )
