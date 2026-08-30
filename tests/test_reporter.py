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
    assert "API Kontrat Degisiklik Raporu" in report
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
    assert "BREAKING" in text or "kirici" in text.lower()
