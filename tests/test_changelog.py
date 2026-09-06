import subprocess
from pathlib import Path

import pytest

from specshift.changelog import ChangelogError, build_changelog, relevant_tags


def _run(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def tagged_repo(tmp_path):
    repo = tmp_path
    _run(["init", "-q"], cwd=repo)
    _run(["config", "user.email", "a@a.com"], cwd=repo)
    _run(["config", "user.name", "a"], cwd=repo)

    spec_path = repo / "openapi.yaml"

    spec_path.write_text(
        "openapi: 3.0.0\ninfo:\n  title: T\n  version: '1.0'\n"
        "paths:\n  /a:\n    get:\n      responses:\n        '200':\n          description: ok\n",
        encoding="utf-8",
    )
    _run(["add", "."], cwd=repo)
    _run(["commit", "-q", "-m", "v1"], cwd=repo)
    _run(["tag", "v1.0.0"], cwd=repo)

    spec_path.write_text(
        "openapi: 3.0.0\ninfo:\n  title: T\n  version: '2.0'\npaths: {}\n",
        encoding="utf-8",
    )
    _run(["add", "."], cwd=repo)
    _run(["commit", "-q", "-m", "v2 - remove endpoint"], cwd=repo)
    _run(["tag", "v2.0.0"], cwd=repo)

    return repo


def test_relevant_tags_returns_chronological_order(tagged_repo):
    tags = relevant_tags("openapi.yaml", repo_path=str(tagged_repo))
    assert tags == ["v1.0.0", "v2.0.0"]


def test_relevant_tags_respects_pattern(tagged_repo):
    tags = relevant_tags("openapi.yaml", pattern="v2*", repo_path=str(tagged_repo))
    assert tags == ["v2.0.0"]


def test_build_changelog_detects_breaking_change_between_tags(tagged_repo):
    tags = relevant_tags("openapi.yaml", repo_path=str(tagged_repo))
    md = build_changelog("openapi.yaml", tags, repo_path=str(tagged_repo), include_working_tree=False)
    assert "v1.0.0 -> v2.0.0" in md
    assert "Breaking" in md


def test_build_changelog_includes_unreleased_working_tree_section(tagged_repo):
    (tagged_repo / "openapi.yaml").write_text(
        "openapi: 3.0.0\ninfo:\n  title: T\n  version: '3.0-dev'\n"
        "paths:\n  /b:\n    get:\n      responses:\n        '200':\n          description: ok\n",
        encoding="utf-8",
    )
    tags = relevant_tags("openapi.yaml", repo_path=str(tagged_repo))
    md = build_changelog("openapi.yaml", tags, repo_path=str(tagged_repo), include_working_tree=True)
    assert "Unreleased" in md


def test_build_changelog_raises_when_nothing_to_compare(tagged_repo):
    with pytest.raises(ChangelogError):
        build_changelog("openapi.yaml", [], repo_path=str(tagged_repo), include_working_tree=False)
