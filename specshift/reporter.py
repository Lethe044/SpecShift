"""DiffResult nesnesini okunabilir raporlara donusturur."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from specshift.models import DiffResult, Severity

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    _HAS_RICH = True
except ImportError:  # rich yuklu degilse duz metne dus
    _HAS_RICH = False

_SEVERITY_COLORS = {
    Severity.BREAKING: "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO: "cyan",
}


def print_console_report(result: DiffResult, verbose: bool = True) -> None:
    """Sonucu terminale renkli sekilde yazdirir. Rich yoksa duz metne duser."""
    if _HAS_RICH:
        _print_rich_report(result, verbose=verbose)
    else:
        print(render_plain_text_report(result, verbose=verbose))


def _print_rich_report(result: DiffResult, verbose: bool) -> None:
    console = Console()
    counts = result.summary_counts()

    header = f"{result.old_title or 'Spesifikasyon'} : {result.old_version} -> {result.new_version}"
    console.print(f"\n[bold]{header}[/bold]")
    console.print(
        f"[bold red]{counts['breaking']} kirici[/bold red], "
        f"[bold yellow]{counts['warning']} uyari[/bold yellow], "
        f"[cyan]{counts['info']} bilgi[/cyan] degisiklik bulundu.\n"
    )

    if result.is_empty:
        console.print("[green]Iki spesifikasyon arasinda fark bulunamadi.[/green]")
        return

    changes = result.sorted_changes() if verbose else result.breaking_changes + result.warnings

    table = Table(show_lines=False, expand=True)
    table.add_column("Seviye", width=10)
    table.add_column("Konum", ratio=1)
    table.add_column("Aciklama", ratio=2)

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
            f"\n[bold red]Sonuc: {counts['breaking']} kirici degisiklik nedeniyle "
            "bu spesifikasyon guncellemesi tuketiciler icin risklidir.[/bold red]"
        )
    else:
        console.print("\n[bold green]Sonuc: kirici degisiklik bulunamadi.[/bold green]")


def render_plain_text_report(result: DiffResult, verbose: bool = True) -> str:
    lines: list[str] = []
    counts = result.summary_counts()

    lines.append(f"{result.old_title or 'Spesifikasyon'} : {result.old_version} -> {result.new_version}")
    lines.append(
        f"{counts['breaking']} kirici, {counts['warning']} uyari, {counts['info']} bilgi degisiklik bulundu."
    )
    lines.append("")

    if result.is_empty:
        lines.append("Iki spesifikasyon arasinda fark bulunamadi.")
        return "\n".join(lines)

    changes = result.sorted_changes() if verbose else result.breaking_changes + result.warnings

    for change in changes:
        lines.append(f"{change.severity.icon} {change.location} :: {change.message}")

    lines.append("")
    if result.has_breaking_changes:
        lines.append(
            f"Sonuc: {counts['breaking']} kirici degisiklik nedeniyle bu guncelleme risklidir."
        )
    else:
        lines.append("Sonuc: kirici degisiklik bulunamadi.")

    return "\n".join(lines)


def render_markdown_report(result: DiffResult, ai_summary: str | None = None) -> str:
    counts = result.summary_counts()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"# API Kontrat Degisiklik Raporu")
    lines.append("")
    lines.append(f"**Kaynak:** {result.old_title or 'API'} ({result.old_version} -> {result.new_version})")
    lines.append(f"**Olusturulma zamani:** {timestamp}")
    lines.append("")

    if result.has_breaking_changes:
        lines.append(f"## Ozet: {counts['breaking']} kirici degisiklik bulundu")
    else:
        lines.append("## Ozet: kirici degisiklik bulunamadi")

    lines.append("")
    lines.append(f"| Seviye | Sayi |")
    lines.append(f"|---|---|")
    lines.append(f"| Kirici (breaking) | {counts['breaking']} |")
    lines.append(f"| Uyari (warning) | {counts['warning']} |")
    lines.append(f"| Bilgi (info) | {counts['info']} |")
    lines.append("")

    if ai_summary:
        lines.append("## Yapay Zeka Ozeti")
        lines.append("")
        lines.append(ai_summary)
        lines.append("")

    for severity, title in (
        (Severity.BREAKING, "Kirici Degisiklikler"),
        (Severity.WARNING, "Uyarilar"),
        (Severity.INFO, "Bilgi Amacli Degisiklikler"),
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
        lines.append("Iki spesifikasyon arasinda hicbir fark bulunamadi.")

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
