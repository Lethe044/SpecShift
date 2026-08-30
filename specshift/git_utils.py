"""Git revizyonlari arasinda dosya icerigi cekmek icin yardimci fonksiyonlar."""

from __future__ import annotations

import subprocess
from pathlib import Path

from specshift.spec_loader import SpecLoadError, parse_spec_text


class GitError(Exception):
    """Git komutu basarisiz oldugunda firlatilir."""


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
        raise GitError("git komutu bulunamadi. Git'in kurulu oldugundan emin olun.") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git komutu basarisiz oldu: {exc.stderr.strip()}") from exc

    return result.stdout


def is_git_repo(path: str = ".") -> bool:
    try:
        _run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return True
    except GitError:
        return False


def load_spec_from_git(file_path: str, ref: str, repo_path: str = ".") -> dict:
    """
    Verilen git referansindaki (ornegin 'main', 'HEAD~1', bir tag veya commit hash)
    dosyanin icerigini okuyup spesifikasyon olarak ayristirir.
    """
    relative_path = Path(file_path)
    try:
        # git repo koku disindan cagrilmis olabilir, yolu repo kokune gore normalize et
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
            f"'{ref}:{git_path}' icerigi okunamadi. Dosya yolunun ve referansin "
            f"dogru oldugundan emin olun. Detay: {exc}"
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
