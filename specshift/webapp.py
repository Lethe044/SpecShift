"""
A small, dependency-free local web dashboard for specshift.

This lets you compare two specifications (OpenAPI, GraphQL, or Protobuf)
from a browser instead of the command line: pick two files, click compare,
and get the same styled, filterable HTML report the CLI produces, with a
short in-session history of past comparisons. It is built entirely on
Python's standard library (http.server), so it adds no new dependency and
works the moment specshift is installed.

This is a local development tool, not a production web application: it
binds to 127.0.0.1 by default, keeps history in memory only (nothing is
written to disk, and everything is lost when the server stops), and is
not intended to be exposed on the public internet.
"""

from __future__ import annotations

import html as html_module
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from specshift.ai_summary import generate_summary
from specshift.differ import diff_specs
from specshift.graphql_differ import diff_graphql
from specshift.models import DiffResult
from specshift.protobuf_differ import diff_protos
from specshift.reporter import render_html_report
from specshift.spec_loader import SpecLoadError, parse_spec_text

_MAX_BODY_BYTES = 20 * 1024 * 1024  # 20 MB, generous for hand-pasted specs

_PAGE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>specshift dashboard</title>
<style>
  :root {{
    --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #c9d1d9;
    --muted: #8b949e; --accent: #58a6ff; --breaking: #f85149;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  nav {{
    display: flex; align-items: center; gap: 1rem; padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border); background: var(--panel);
  }}
  nav .brand {{ font-weight: 700; font-size: 1.1rem; }}
  nav .brand span {{ color: var(--accent); }}
  nav a {{ color: var(--muted); text-decoration: none; font-size: 0.9rem; }}
  nav a:hover {{ color: var(--text); }}
  .layout {{ display: flex; min-height: calc(100vh - 57px); }}
  aside {{
    width: 260px; border-right: 1px solid var(--border); padding: 1rem;
    background: var(--panel); flex-shrink: 0;
  }}
  aside h3 {{ font-size: 0.8rem; text-transform: uppercase; color: var(--muted); margin-bottom: 0.75rem; }}
  aside ul {{ list-style: none; padding: 0; margin: 0; }}
  aside li {{ margin-bottom: 0.5rem; }}
  aside a {{
    display: block; padding: 0.5rem 0.6rem; border-radius: 6px; color: var(--text);
    text-decoration: none; font-size: 0.85rem; border: 1px solid transparent;
  }}
  aside a:hover {{ border-color: var(--border); background: rgba(255,255,255,0.03); }}
  aside .empty {{ color: var(--muted); font-size: 0.85rem; }}
  main {{ flex: 1; padding: 2rem; max-width: 900px; }}
  h1 {{ font-size: 1.3rem; margin-top: 0; }}
  form {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; }}
  .row {{ display: flex; gap: 1rem; margin-bottom: 1rem; }}
  .col {{ flex: 1; }}
  label {{ display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 0.4rem; }}
  select, textarea {{
    width: 100%; background: #0d1117; border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); padding: 0.6rem; font-family: inherit; font-size: 0.9rem;
  }}
  textarea {{ min-height: 220px; font-family: "SFMono-Regular", Consolas, monospace; font-size: 0.8rem; resize: vertical; }}
  .file-row {{ display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; }}
  input[type="file"] {{ font-size: 0.8rem; color: var(--muted); }}
  button {{
    background: var(--accent); color: #0d1117; border: none; border-radius: 6px;
    padding: 0.7rem 1.4rem; font-weight: 700; cursor: pointer; font-size: 0.95rem;
  }}
  button:hover {{ opacity: 0.9; }}
  .hint {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.5rem; }}
  .error {{ background: rgba(248,81,73,0.1); border: 1px solid var(--breaking); border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; color: var(--breaking); }}
  .report-frame {{ border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
  iframe {{ width: 100%; height: 80vh; border: none; background: #0d1117; }}
</style>
</head>
<body>
<nav>
  <div class="brand">spec<span>shift</span> dashboard</div>
  <a href="/">New comparison</a>
  <a href="https://github.com/Lethe044/SpecShift" target="_blank" rel="noopener">GitHub</a>
</nav>
<div class="layout">
  <aside>
    <h3>Recent comparisons</h3>
    {history}
  </aside>
  <main>
    {content}
  </main>
</div>
</body>
</html>
"""

_FORM_HTML = """
<h1>Compare two contract files</h1>
{error_block}
<form method="post" action="/compare">
  <div class="row">
    <div class="col">
      <label for="format-select">Contract type</label>
      <select name="kind" id="format-select">
        <option value="auto">Auto-detect</option>
        <option value="openapi">OpenAPI / Swagger</option>
        <option value="graphql">GraphQL SDL</option>
        <option value="proto">Protobuf / gRPC</option>
      </select>
    </div>
    <div class="col">
      <label>&nbsp;</label>
      <label style="display:flex; align-items:center; gap:0.4rem; font-size:0.85rem; color:var(--text);">
        <input type="checkbox" name="ai" value="1" style="width:auto;"> Generate AI summary (uses GROQ_API_KEY / GEMINI_API_KEY if set)
      </label>
    </div>
  </div>
  <div class="row">
    <div class="col">
      <label>Old version</label>
      <div class="file-row">
        <input type="file" onchange="readFile(this, 'old_content')">
        <span class="hint">or paste below</span>
      </div>
      <textarea name="old_content" id="old_content" placeholder="Paste the old spec here..."></textarea>
    </div>
    <div class="col">
      <label>New version</label>
      <div class="file-row">
        <input type="file" onchange="readFile(this, 'new_content')">
        <span class="hint">or paste below</span>
      </div>
      <textarea name="new_content" id="new_content" placeholder="Paste the new spec here..."></textarea>
    </div>
  </div>
  <button type="submit">Compare</button>
  <p class="hint">Everything runs locally in this process. Nothing is uploaded anywhere.</p>
</form>
<script>
function readFile(input, targetId) {{
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {{
    document.getElementById(targetId).value = e.target.result;
  }};
  reader.readAsText(file);
}}
</script>
"""

_history_lock = threading.Lock()
_history: list[dict] = []


def _detect_kind(old_text: str, new_text: str) -> str:
    combined = f"{old_text}\n{new_text}"
    if "openapi:" in combined or "swagger:" in combined or combined.strip().startswith("{"):
        return "openapi"
    if "syntax" in combined and ("message " in combined or "service " in combined):
        return "proto"
    if "type " in combined or "input " in combined or "enum " in combined:
        return "graphql"
    return "openapi"


def _run_diff(kind: str, old_text: str, new_text: str) -> DiffResult:
    if kind == "graphql":
        return diff_graphql(old_text, new_text)
    if kind == "proto":
        return diff_protos(old_text, new_text)
    old_spec = parse_spec_text(old_text, hint="old")
    new_spec = parse_spec_text(new_text, hint="new")
    return diff_specs(old_spec, new_spec)


def _render_history_list() -> str:
    with _history_lock:
        items = list(reversed(_history))

    if not items:
        return '<p class="empty">No comparisons yet.</p>'

    rows = []
    for entry in items:
        counts = entry["counts"]
        label = html_module.escape(entry["label"])
        badge = f"{counts['breaking']}B / {counts['warning']}W / {counts['info']}I"
        rows.append(f'<li><a href="/history/{entry["id"]}">{label}<br><small>{badge}</small></a></li>')

    return "<ul>" + "\n".join(rows) + "</ul>"


def _render_page(content: str) -> str:
    return _PAGE_SHELL.format(history=_render_history_list(), content=content)


def _render_form(error: str = "") -> str:
    error_block = f'<div class="error">{html_module.escape(error)}</div>' if error else ""
    return _FORM_HTML.format(error_block=error_block)


def _store_history(kind: str, result: DiffResult, html_report: str) -> int:
    with _history_lock:
        entry_id = len(_history) + 1
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        title = result.old_title or kind
        label = f"{title} ({kind}) - {timestamp}"
        _history.append(
            {
                "id": entry_id,
                "label": label,
                "counts": result.summary_counts(),
                "html": html_report,
            }
        )
    return entry_id


class _DashboardHandler(BaseHTTPRequestHandler):
    server_version = "specshift-dashboard/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches base class signature
        pass  # keep the CLI output clean; this is a local dev tool

    def _send_html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/" or self.path == "":
            self._send_html(_render_page(_render_form()))
            return

        if self.path.startswith("/history/"):
            try:
                entry_id = int(self.path.rsplit("/", 1)[-1])
            except ValueError:
                entry_id = -1
            with _history_lock:
                entry = next((e for e in _history if e["id"] == entry_id), None)
            if entry is None:
                self._send_html(_render_page("<p>Comparison not found.</p>"), status=404)
                return
            frame = f'<div class="report-frame"><iframe srcdoc="{html_module.escape(entry["html"])}"></iframe></div>'
            self._send_html(_render_page(frame))
            return

        self._send_html(_render_page("<p>Not found.</p>"), status=404)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/compare":
            self._send_html(_render_page("<p>Not found.</p>"), status=404)
            return

        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > _MAX_BODY_BYTES:
            self._send_html(_render_page(_render_form("Request body is empty or too large.")), status=400)
            return

        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        fields = parse_qs(raw_body)

        old_content = fields.get("old_content", [""])[0]
        new_content = fields.get("new_content", [""])[0]
        kind = fields.get("kind", ["auto"])[0]
        want_ai = fields.get("ai", [""])[0] == "1"

        if not old_content.strip() or not new_content.strip():
            self._send_html(_render_page(_render_form("Please provide both an old and a new version.")))
            return

        if kind == "auto":
            kind = _detect_kind(old_content, new_content)

        try:
            result = _run_diff(kind, old_content, new_content)
        except SpecLoadError as exc:
            self._send_html(_render_page(_render_form(f"Could not parse the input: {exc}")))
            return
        except Exception as exc:  # noqa: BLE001 - surface any parser error to the user instead of a raw 500
            self._send_html(_render_page(_render_form(f"Could not compare the input: {exc}")))
            return

        ai_summary = None
        if want_ai:
            ai_summary = generate_summary(result)

        html_report = render_html_report(result, ai_summary=ai_summary)
        _store_history(kind, result, html_report)

        frame = f'<div class="report-frame"><iframe srcdoc="{html_module.escape(html_report)}"></iframe></div>'
        self._send_html(_render_page(frame))


def run_server(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = True) -> None:
    """Starts the local dashboard server and blocks until interrupted (Ctrl+C)."""
    server = ThreadingHTTPServer((host, port), _DashboardHandler)
    url = f"http://{host}:{port}/"

    print(f"specshift dashboard running at {url}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
