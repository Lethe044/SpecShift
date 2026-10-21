from specshift.multi_diff import diff_directories


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


OPENAPI_EMPTY = "openapi: 3.0.0\ninfo:\n  title: T\n  version: '1.0'\npaths: {}\n"


def test_identical_directories_produce_no_changes(tmp_path):
    _write(tmp_path / "old" / "api.yaml", OPENAPI_EMPTY)
    _write(tmp_path / "new" / "api.yaml", OPENAPI_EMPTY)
    assert diff_directories(str(tmp_path / "old"), str(tmp_path / "new")).is_empty


def test_removed_file_is_breaking(tmp_path):
    _write(tmp_path / "old" / "api.yaml", OPENAPI_EMPTY)
    (tmp_path / "new").mkdir()
    result = diff_directories(str(tmp_path / "old"), str(tmp_path / "new"))
    assert any(c.location == "api.yaml" for c in result.breaking_changes)


def test_added_file_is_info(tmp_path):
    (tmp_path / "old").mkdir()
    _write(tmp_path / "new" / "api.yaml", OPENAPI_EMPTY)
    result = diff_directories(str(tmp_path / "old"), str(tmp_path / "new"))
    assert not result.has_breaking_changes
    assert any(c.location == "api.yaml" for c in result.info_changes)


def test_modified_openapi_file_is_diffed_with_prefixed_location(tmp_path):
    _write(
        tmp_path / "old" / "users.yaml",
        "openapi: 3.0.0\ninfo:\n  title: T\n  version: '1.0'\n"
        "paths:\n  /a:\n    get:\n      responses:\n        '200':\n          description: ok\n",
    )
    _write(tmp_path / "new" / "users.yaml", OPENAPI_EMPTY)
    result = diff_directories(str(tmp_path / "old"), str(tmp_path / "new"))
    assert any(c.location.startswith("users.yaml :: ") for c in result.breaking_changes)


def test_mixed_file_types_use_the_right_engine(tmp_path):
    _write(tmp_path / "old" / "schema.graphql", "type Query { x: String } type User { id: ID! name: String }")
    _write(tmp_path / "new" / "schema.graphql", "type Query { x: String } type User { id: ID! }")
    _write(tmp_path / "old" / "service.proto", "message M { string id = 1; }")
    _write(tmp_path / "new" / "service.proto", "message M { int32 id = 1; }")
    result = diff_directories(str(tmp_path / "old"), str(tmp_path / "new"))
    assert any(c.location.startswith("schema.graphql :: ") for c in result.changes)
    assert any(c.location.startswith("service.proto :: ") for c in result.changes)


def test_unmatched_file_types_are_ignored(tmp_path):
    _write(tmp_path / "old" / "README.md", "hello")
    _write(tmp_path / "new" / "README.md", "hello world")
    assert diff_directories(str(tmp_path / "old"), str(tmp_path / "new")).is_empty


def test_custom_pattern_restricts_files(tmp_path):
    _write(tmp_path / "old" / "a.yaml", OPENAPI_EMPTY)
    _write(tmp_path / "old" / "b.proto", "message M { string id = 1; }")
    (tmp_path / "new").mkdir()
    result = diff_directories(str(tmp_path / "old"), str(tmp_path / "new"), patterns=("*.proto",))
    assert [c.location for c in result.breaking_changes] == ["b.proto"]
