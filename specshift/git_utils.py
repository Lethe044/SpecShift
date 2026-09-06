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


def _resolve_git_path(file_path: str, repo_path: str = ".") -> str:
    """Normalizes a file path to be relative to the repository root, as git expects."""
    relative_path = Path(file_path)
    try:
        toplevel = _run_git(["rev-parse", "--show-toplevel"], cwd=repo_path).strip()
        repo_root = Path(toplevel)
        abs_target = (Path(repo_path).resolve() / relative_path).resolve()
        rel_to_root = abs_target.relative_to(repo_root)
        return str(rel_to_root).replace("\\", "/")
    except (GitError, ValueError):
        return str(relative_path).replace("\\", "/")


def load_spec_from_git(file_path: str, ref: str, repo_path: str = ".") -> dict:
    """
    Reads the content of a file at a given git reference (e.g. 'main',
    'HEAD~1', a tag, or a commit hash) and parses it as a specification.
    """
    git_path = _resolve_git_path(file_path, repo_path)

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


def read_file_at_ref(file_path: str, ref: str, repo_path: str = ".") -> str:
    """Reads the raw text content of a file at a given git reference, without parsing it."""
    git_path = _resolve_git_path(file_path, repo_path)
    try:
        return _run_git(["show", f"{ref}:{git_path}"], cwd=repo_path)
    except GitError as exc:
        raise GitError(
            f"Could not read '{ref}:{git_path}'. Make sure the file path and reference are correct. "
            f"Details: {exc}"
        ) from exc


def file_exists_at_ref(file_path: str, ref: str, repo_path: str = ".") -> bool:
    """Returns True if the given file exists at the given git reference."""
    git_path = _resolve_git_path(file_path, repo_path)
    try:
        _run_git(["cat-file", "-e", f"{ref}:{git_path}"], cwd=repo_path)
        return True
    except GitError:
        return False


def list_tags_chronological(repo_path: str = ".") -> list[str]:
    """
    Returns all git tags in chronological (creation) order, oldest first.
    Uses for-each-ref rather than 'git tag --sort', which behaves more
    consistently across both lightweight and annotated tags.
    """
    try:
        output = _run_git(
            ["for-each-ref", "--sort=creatordate", "--format=%(refname:short)", "refs/tags"],
            cwd=repo_path,
        )
    except GitError:
        return []

    return [line.strip() for line in output.splitlines() if line.strip()]


def tag_date(tag: str, repo_path: str = ".") -> str:
    """Returns the ISO creation date of a tag, or an empty string if unavailable."""
    try:
        output = _run_git(
            ["for-each-ref", "--format=%(creatordate:short)", f"refs/tags/{tag}"],
            cwd=repo_path,
        )
        return output.strip()
    except GitError:
        return ""


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
