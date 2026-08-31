"""Helper functions for reading file content across git revisions."""

from __future__ import annotations

import subprocess
from pathlib import Path

from specshift.spec_loader import SpecLoadError, parse_spec_text


class GitError(Exception):
    """Raised when a git command fails."""


def _run_git(args: list[str], cwd: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GitError("git command not found. Make sure git is installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git command failed: {exc.stderr.strip()}") from exc

    return result.stdout


def is_git_repo(path: str = ".") -> bool:
    try:
        _run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return True
    except GitError:
        return False


def load_spec_from_git(file_path: str, ref: str, repo_path: str = ".") -> dict:
    """
    Reads the content of a file at a given git reference (e.g. 'main',
    'HEAD~1', a tag, or a commit hash) and parses it as a specification.
    """
    relative_path = Path(file_path)
    try:
        # The command may be invoked from outside the repo root, so
        # normalize the path relative to the repository root.
        toplevel = _run_git(["rev-parse", "--show-toplevel"], cwd=repo_path).strip()
        repo_root = Path(toplevel)
        abs_target = (Path(repo_path).resolve() / relative_path).resolve()
        rel_to_root = abs_target.relative_to(repo_root)
        git_path = str(rel_to_root).replace("\\", "/")
    except (GitError, ValueError):
        git_path = str(relative_path).replace("\\", "/")

    try:
        content = _run_git(["show", f"{ref}:{git_path}"], cwd=repo_path)
    except GitError as exc:
        raise GitError(
            f"Could not read '{ref}:{git_path}'. Make sure the file path and "
            f"reference are correct. Details: {exc}"
        ) from exc

    try:
        return parse_spec_text(content, hint=f"{ref}:{git_path}")
    except SpecLoadError as exc:
        raise GitError(str(exc)) from exc


def current_branch(repo_path: str = ".") -> str:
    try:
        return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path).strip()
    except GitError:
        return "unknown"


def short_sha(ref: str = "HEAD", repo_path: str = ".") -> str:
    try:
        return _run_git(["rev-parse", "--short", ref], cwd=repo_path).strip()
    except GitError:
        return ref
