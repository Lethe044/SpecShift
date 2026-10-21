"""
Generates a natural-language summary from a DiffResult.

This module is entirely optional. If neither GROQ_API_KEY nor GEMINI_API_KEY
is set, a rule-based summary is produced without making any network calls.
This keeps the project fully functional without depending on any paid
service.
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from specshift.models import DiffResult, Severity

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

OPENAI_COMPATIBLE_URL_ENV = "SPECSHIFT_OPENAI_BASE_URL"


class AISummaryError(Exception):
    """Raised when the AI summary could not be generated."""


def generate_summary(
    result: DiffResult,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 30,
    context: str = "diff",
) -> str:
    """
    Returns a natural-language summary using a configured AI provider when
    possible, otherwise falls back to a rule-based summary. Never raises an
    exception that would halt execution; failures fall back silently.

    context is either "diff" (comparing two versions, the default) or
    "lint" (findings about a single specification), and selects which
    prompt and fallback wording is used.
    """
    prompt = _build_prompt(result, context=context)

    chosen_provider = provider or _detect_provider()

    if chosen_provider == "groq" and os.environ.get("GROQ_API_KEY"):
        try:
            return _call_groq(prompt, model or GROQ_DEFAULT_MODEL, timeout)
        except AISummaryError:
            pass

    if chosen_provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        try:
            return _call_gemini(prompt, model or GEMINI_DEFAULT_MODEL, timeout)
        except AISummaryError:
            pass

    if chosen_provider == "openai_compatible" and os.environ.get("SPECSHIFT_API_KEY"):
        try:
            return _call_openai_compatible(prompt, model, timeout)
        except AISummaryError:
            pass

    return build_template_summary(result, context=context)


def _detect_provider() -> Optional[str]:
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("SPECSHIFT_API_KEY") and os.environ.get(OPENAI_COMPATIBLE_URL_ENV):
        return "openai_compatible"
    return None


def _build_prompt(result: DiffResult, context: str = "diff") -> str:
    counts = result.summary_counts()

    if context == "lint":
        intro = (
            "Below is a list of issues found while linting a single API "
            "schema or specification for correctness and best practices. This is NOT a "
            "comparison between two versions, it is a quality review of one "
            "document. Read this list and write a short, clear, professional "
            "summary in English that a developer maintaining this API would "
            "understand. First highlight any spec-validity issues (things that "
            "could break tooling or fail parsing), then best-practice gaps, "
            "then minor style suggestions. Do not use lists or headings, write "
            "in flowing paragraphs. Do not invent information, base the "
            "summary only on the findings given.",
        )
        total_label = "issues"
    else:
        intro = (
            "Below is a list of contract changes detected between two versions "
            "of an API. Read this list and write a short, clear, professional "
            "summary in English that a developer consuming this API would "
            "understand. First highlight the most important breaking changes, "
            "then anything worth paying attention to, and finally briefly "
            "mention minor additions. Do not use lists or headings, write in "
            "flowing paragraphs. Do not invent information, base the summary "
            "only on the changes given.",
        )
        total_label = "changes"

    lines = [
        intro[0],
        "",
        f"Total: {counts['breaking']} breaking, {counts['warning']} warning, {counts['info']} informational {total_label}.",
        "",
    ]
    for change in result.sorted_changes()[:60]:
        lines.append(f"- [{change.severity.value}] {change.location}: {change.message}")

    return "\n".join(lines)


def _call_groq(prompt: str, model: str, timeout: int) -> str:
    api_key = os.environ["GROQ_API_KEY"]
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AISummaryError(f"Groq request failed: {exc}") from exc


def _call_gemini(prompt: str, model: str, timeout: int) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    url = GEMINI_API_URL_TEMPLATE.format(model=model, key=api_key)
    try:
        response = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AISummaryError(f"Gemini request failed: {exc}") from exc


def _call_openai_compatible(prompt: str, model: Optional[str], timeout: int) -> str:
    api_key = os.environ["SPECSHIFT_API_KEY"]
    base_url = os.environ[OPENAI_COMPATIBLE_URL_ENV].rstrip("/")
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "default",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AISummaryError(f"Custom endpoint request failed: {exc}") from exc


def build_template_summary(result: DiffResult, context: str = "diff") -> str:
    """A deterministic, rule-based summary that works without any API key."""
    if context == "lint":
        return _build_lint_template_summary(result)
    return _build_diff_template_summary(result)


def _build_diff_template_summary(result: DiffResult) -> str:
    counts = result.summary_counts()

    if result.is_empty:
        return "No differences were detected between the two specifications."

    parts: list[str] = []

    if counts["breaking"] > 0:
        top_breaking = result.breaking_changes[:5]
        breaking_desc = "; ".join(f"{c.location} ({c.message.rstrip('.')})" for c in top_breaking)
        extra = counts["breaking"] - len(top_breaking)
        extra_note = f" and {extra} more breaking change(s)" if extra > 0 else ""
        parts.append(
            f"This update contains {counts['breaking']} breaking change(s) and may affect "
            f"existing API consumers. Notably: {breaking_desc}{extra_note}. "
            "Clients using this API should review these points before migrating."
        )
    else:
        parts.append(
            "This update does not contain any breaking changes, existing clients "
            "can continue working without any additional action."
        )

    if counts["warning"] > 0:
        parts.append(
            f"There are also {counts['warning']} change(s) worth paying attention to; "
            "these are not directly breaking but may cause behavioral differences "
            "in some usage scenarios."
        )

    if counts["info"] > 0:
        parts.append(
            f"The remaining {counts['info']} change(s) are new features or improvements "
            "and do not pose a risk to existing integrations."
        )

    return " ".join(parts)


def _build_lint_template_summary(result: DiffResult) -> str:
    counts = result.summary_counts()

    if result.is_empty:
        return "No issues were found; this specification looks clean."

    parts: list[str] = []

    if counts["breaking"] > 0:
        top_issues = result.breaking_changes[:5]
        issue_desc = "; ".join(f"{c.location} ({c.message.rstrip('.')})" for c in top_issues)
        extra = counts["breaking"] - len(top_issues)
        extra_note = f" and {extra} more" if extra > 0 else ""
        parts.append(
            f"This specification has {counts['breaking']} spec-validity issue(s) that should be "
            f"fixed first, since they can break tooling or code generation. Notably: {issue_desc}{extra_note}."
        )
    else:
        parts.append("This specification has no spec-validity issues.")

    if counts["warning"] > 0:
        parts.append(
            f"There are {counts['warning']} best-practice recommendation(s), such as missing "
            "descriptions, operation IDs, or documented error responses, that would improve the "
            "developer experience for anyone consuming this API."
        )

    if counts["info"] > 0:
        parts.append(
            f"The remaining {counts['info']} finding(s) are minor style or cleanup suggestions."
        )

    return " ".join(parts)
