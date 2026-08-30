import json
import os

from specshift.cli import main


def test_cli_diff_returns_nonzero_on_breaking_change(tmp_path, capsys):
    old_file = tmp_path / "old.yaml"
    new_file = tmp_path / "new.yaml"
    old_file.write_text(
        "openapi: 3.0.0\ninfo:\n  title: D\n  version: '1.0'\npaths:\n  /a:\n    get:\n      responses:\n        '200':\n          description: ok\n",
        encoding="utf-8",
    )
    new_file.write_text("openapi: 3.0.0\ninfo:\n  title: D\n  version: '2.0'\npaths: {}\n", encoding="utf-8")

    exit_code = main(["diff", str(old_file), str(new_file), "--format", "json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 1
    assert data["has_breaking_changes"] is True


def test_cli_diff_returns_zero_when_no_breaking_change(tmp_path, capsys):
    old_file = tmp_path / "old.yaml"
    new_file = tmp_path / "new.yaml"
    content = "openapi: 3.0.0\ninfo:\n  title: D\n  version: '1.0'\npaths:\n  /a:\n    get:\n      responses:\n        '200':\n          description: ok\n"
    old_file.write_text(content, encoding="utf-8")
    new_file.write_text(content, encoding="utf-8")

    exit_code = main(["diff", str(old_file), str(new_file), "--format", "json"])
    assert exit_code == 0


def test_cli_init_creates_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0
    assert (tmp_path / ".specshift.yml").exists()


def test_cli_init_refuses_overwrite_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    exit_code = main(["init"])
    assert exit_code == 1
