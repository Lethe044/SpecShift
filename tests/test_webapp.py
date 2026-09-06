import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from specshift.webapp import _detect_kind, run_server


@pytest.fixture(scope="module")
def dashboard_url():
    port = 8798
    thread = threading.Thread(
        target=run_server, kwargs={"host": "127.0.0.1", "port": port, "open_browser": False}, daemon=True
    )
    thread.start()
    time.sleep(0.8)
    yield f"http://127.0.0.1:{port}"


def test_detect_kind_openapi():
    assert _detect_kind("openapi: 3.0.0", "openapi: 3.0.0") == "openapi"


def test_detect_kind_graphql():
    assert _detect_kind("type User { id: ID! }", "type User { id: ID! }") == "graphql"


def test_detect_kind_proto():
    assert _detect_kind('syntax = "proto3"; message M {}', 'syntax = "proto3"; message M {}') == "proto"


def test_index_page_serves_form(dashboard_url):
    response = urllib.request.urlopen(f"{dashboard_url}/", timeout=5)
    body = response.read().decode("utf-8")
    assert response.status == 200
    assert "Compare two contract files" in body


def test_compare_openapi_specs_returns_report(dashboard_url):
    old_spec = 'openapi: 3.0.0\ninfo:\n  title: Demo\n  version: "1.0"\npaths:\n  /a:\n    get:\n      responses:\n        "200":\n          description: ok\n'
    new_spec = 'openapi: 3.0.0\ninfo:\n  title: Demo\n  version: "2.0"\npaths: {}\n'
    data = urllib.parse.urlencode({"old_content": old_spec, "new_content": new_spec, "kind": "auto"}).encode()
    response = urllib.request.urlopen(f"{dashboard_url}/compare", data=data, timeout=5)
    body = response.read().decode("utf-8")
    assert response.status == 200
    assert "report-frame" in body


def test_compare_missing_input_shows_error(dashboard_url):
    data = urllib.parse.urlencode({"old_content": "", "new_content": "", "kind": "auto"}).encode()
    response = urllib.request.urlopen(f"{dashboard_url}/compare", data=data, timeout=5)
    body = response.read().decode("utf-8")
    assert "Please provide both" in body


def test_unknown_path_returns_404(dashboard_url):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(f"{dashboard_url}/does-not-exist", timeout=5)
    assert excinfo.value.code == 404
