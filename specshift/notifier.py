"""Sends diff results via Slack or Discord webhooks."""

from __future__ import annotations

import requests

from specshift.models import DiffResult


class NotifyError(Exception):
    """Raised when a notification could not be sent."""


def notify_slack(webhook_url: str, result: DiffResult, ai_summary: str | None = None, timeout: int = 15) -> None:
    counts = result.summary_counts()
    color = "#e01e5a" if result.has_breaking_changes else ("#ecb22e" if counts["warning"] else "#2eb67d")

    title = f"{result.old_title or 'API'} contract change: {result.old_version} -> {result.new_version}"
    summary_line = f"{counts['breaking']} breaking, {counts['warning']} warning, {counts['info']} info changes"

    fields = []
    for change in result.breaking_changes[:10]:
        fields.append({"title": change.location, "value": change.message, "short": False})

    payload = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": summary_line + ("\n\n" + ai_summary if ai_summary else ""),
                "fields": fields,
            }
        ]
    }

    _post(webhook_url, payload, timeout)


def notify_discord(webhook_url: str, result: DiffResult, ai_summary: str | None = None, timeout: int = 15) -> None:
    counts = result.summary_counts()
    color = 0xE01E5A if result.has_breaking_changes else (0xECB22E if counts["warning"] else 0x2EB67D)

    title = f"{result.old_title or 'API'} contract change"
    description = (
        f"**{result.old_version} -> {result.new_version}**\n"
        f"{counts['breaking']} breaking, {counts['warning']} warning, {counts['info']} info changes found."
    )
    if ai_summary:
        description += f"\n\n{ai_summary[:1500]}"

    fields = [
        {"name": change.location[:256], "value": change.message[:1024], "inline": False}
        for change in result.breaking_changes[:10]
    ]

    payload = {"embeds": [{"title": title, "description": description[:4000], "color": color, "fields": fields}]}

    _post(webhook_url, payload, timeout)


def _post(webhook_url: str, payload: dict, timeout: int) -> None:
    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NotifyError(f"Failed to send webhook: {exc}") from exc
