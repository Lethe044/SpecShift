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


def test_cli_diff_sarif_format_produces_valid_json(tmp_path, capsys):
    old_file = tmp_path / "old.yaml"
    new_file = tmp_path / "new.yaml"
    old_file.write_text(
        "openapi: 3.0.0\ninfo:\n  title: D\n  version: '1.0'\npaths:\n  /a:\n    get:\n      responses:\n        '200':\n          description: ok\n",
        encoding="utf-8",
    )
    new_file.write_text("openapi: 3.0.0\ninfo:\n  title: D\n  version: '2.0'\npaths: {}\n", encoding="utf-8")

    output_path = tmp_path / "results.sarif"
    exit_code = main(
        ["diff", str(old_file), str(new_file), "--format", "sarif", "--output", str(output_path), "--fail-on", "none"]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    assert data["version"] == "2.1.0"


def test_cli_diff_graphql_works(tmp_path):
    old_file = tmp_path / "old.graphql"
    new_file = tmp_path / "new.graphql"
    old_file.write_text("type User { id: ID! name: String }", encoding="utf-8")
    new_file.write_text("type User { id: ID! }", encoding="utf-8")

    exit_code = main(["diff-graphql", str(old_file), str(new_file), "--format", "json", "--fail-on", "breaking"])
    assert exit_code == 1


def test_cli_diff_proto_works(tmp_path):
    old_file = tmp_path / "old.proto"
    new_file = tmp_path / "new.proto"
    old_file.write_text("message M { string id = 1; }", encoding="utf-8")
    new_file.write_text("message M { int32 id = 1; }", encoding="utf-8")

    exit_code = main(["diff-proto", str(old_file), str(new_file), "--format", "json", "--fail-on", "breaking"])
    assert exit_code == 1


def test_cli_lint_flags_missing_operation_id(tmp_path, capsys):
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(
        "openapi: 3.0.0\ninfo:\n  title: T\n  version: '1.0'\n"
        "paths:\n  /a:\n    get:\n      responses:\n        '200':\n          description: ok\n",
        encoding="utf-8",
    )
    exit_code = main(["lint", str(spec_file), "--format", "json", "--fail-on", "none"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert any("operationId" in c["message"] for c in data["changes"])


def test_cli_lint_clean_spec_has_no_findings(tmp_path):
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(
        "openapi: 3.0.0\ninfo:\n  title: T\n  version: '1.0'\n  description: d\n"
        "paths:\n  /a:\n    get:\n      operationId: getA\n      summary: s\n"
        "      responses:\n        '200':\n          description: ok\n",
        encoding="utf-8",
    )
    exit_code = main(["lint", str(spec_file), "--fail-on", "breaking"])
    assert exit_code == 0
