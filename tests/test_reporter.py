import json

from specshift.differ import diff_specs
from specshift.reporter import render_json_report, render_markdown_report, render_plain_text_report


def make_result():
    old = {
        "info": {"title": "Demo", "version": "1.0.0"},
        "paths": {"/a": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }
    new = {
        "info": {"title": "Demo", "version": "2.0.0"},
        "paths": {},
    }
    return diff_specs(old, new)


def test_render_markdown_report_contains_summary():
    result = make_result()
    report = render_markdown_report(result)
    assert "API Contract Change Report" in report
    assert "1.0.0" in report
    assert "2.0.0" in report


def test_render_json_report_is_valid_json():
    result = make_result()
    report = render_json_report(result)
    parsed = json.loads(report)
    assert parsed["has_breaking_changes"] is True
    assert parsed["summary"]["breaking"] >= 1


def test_render_plain_text_report_lists_changes():
    result = make_result()
    text = render_plain_text_report(result)
    assert "BREAKING" in text or "breaking" in text.lower()


def test_render_html_report_contains_table_and_data():
    from specshift.reporter import render_html_report

    result = make_result()
    html = render_html_report(result)
    assert "<table" in html
    assert "Demo" in html
    assert "data-severity=\"breaking\"" in html


def test_render_html_report_embeds_ai_summary():
    from specshift.reporter import render_html_report

    result = make_result()
    html = render_html_report(result, ai_summary="This is a test summary.")
    assert "This is a test summary." in html
    assert "ai-summary" in html


def test_render_sarif_report_is_valid_structure():
    from specshift.reporter import render_sarif_report

    result = make_result()
    sarif_text = render_sarif_report(result, artifact_path="openapi.yaml")
    sarif = json.loads(sarif_text)

    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["tool"]["driver"]["name"] == "specshift"
    assert len(sarif["runs"][0]["results"]) == len(result.changes)
    first_result = sarif["runs"][0]["results"][0]
    assert first_result["level"] == "error"
    assert first_result["ruleId"] == "specshift-breaking-change"
    assert first_result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "openapi.yaml"


def test_render_sarif_report_maps_all_severity_levels():
    from specshift.differ import diff_specs
    from specshift.reporter import render_sarif_report

    old = {
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/a": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/b": {"get": {"responses": {"200": {"description": "ok"}}}},
        },
    }
    new = {
        "info": {"title": "T", "version": "2.0"},
        "paths": {"/b": {"get": {"responses": {"200": {"description": "ok"}}}}, "/c": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }
    result = diff_specs(old, new)
    sarif = json.loads(render_sarif_report(result))
    levels = {r["level"] for r in sarif["runs"][0]["results"]}
    assert "error" in levels
    assert "note" in levels
