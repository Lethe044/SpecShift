"""
Reads a specshift JSON report and writes the summary counts to the
GITHUB_OUTPUT file so they can be used by later steps or by whatever
workflow consumes this action.

Usage: python3 parse_summary.py <path-to-json-report>
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: parse_summary.py <path-to-json-report>", file=sys.stderr)
        return 1

    report_path = sys.argv[1]

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read or parse '{report_path}': {exc}", file=sys.stderr)
        return 1

    summary = data.get("summary", {})
    has_breaking = bool(data.get("has_breaking_changes", False))

    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        print("GITHUB_OUTPUT environment variable is not set.", file=sys.stderr)
        return 1

    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"has_breaking_changes={'true' if has_breaking else 'false'}\n")
        f.write(f"breaking_count={summary.get('breaking', 0)}\n")
        f.write(f"warning_count={summary.get('warning', 0)}\n")
        f.write(f"info_count={summary.get('info', 0)}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
