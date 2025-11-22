"""Server tests using urllib + a real localhost socket."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import HTTPServer

import pytest

from snippetbox import server, storage


@pytest.fixture
def running_server(tmp_path, python_snippet):
    book = storage.Book.init(tmp_path / "book.json")
    book.add(python_snippet)
    book.save()
    httpd = server.make_server(book.path, host="127.0.0.1", port=0)
    actual_port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, actual_port, python_snippet
    httpd.shutdown()
    httpd.server_close()


def _get(port: int, path: str) -> tuple:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def test_healthz_returns_ok(running_server):
    _, port, _ = running_server
    status, body = _get(port, "/healthz")
    assert status == 200
    assert "ok" in body


def test_index_returns_html(running_server):
    _, port, _ = running_server
    status, body = _get(port, "/")
    assert status == 200
    assert "<html>" in body


def test_api_snippets_returns_json(running_server):
    _, port, snippet = running_server
    status, body = _get(port, "/api/snippets")
    assert status == 200
    data = json.loads(body)
    assert any(s["id"] == snippet.id for s in data)


def test_api_snippet_by_id(running_server):
    _, port, snippet = running_server
    status, body = _get(port, f"/api/snippet/{snippet.id}")
    assert status == 200
    assert json.loads(body)["id"] == snippet.id


def test_api_snippet_missing_returns_404(running_server):
    _, port, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _get(port, "/api/snippet/missing-id")
    assert exc_info.value.code == 404


def test_snippet_by_slug(running_server):
    _, port, snippet = running_server
    status, body = _get(port, f"/snippet/{snippet.slug}")
    assert status == 200
    assert "<html>" in body


def test_snippet_by_slug_missing(running_server):
    _, port, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _get(port, "/snippet/no-such-slug")
    assert exc_info.value.code == 404


def test_unknown_path_returns_404(running_server):
    _, port, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _get(port, "/random-thing")
    assert exc_info.value.code == 404


def test_make_server_returns_http_server(tmp_path):
    storage.Book.init(tmp_path / "book.json")
    httpd = server.make_server(tmp_path / "book.json", port=0)
    assert isinstance(httpd, HTTPServer)
    httpd.server_close()


def test_make_server_with_missing_book_handles_request(tmp_path):
    httpd = server.make_server(tmp_path / "missing.json", port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _get(port, "/")
        assert exc_info.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_reachable_open_port(running_server):
    _, port, _ = running_server
    assert server.reachable("127.0.0.1", port) is True


def test_reachable_closed_port():
    assert server.reachable("127.0.0.1", 1, timeout=0.1) is False


def test_handler_log_message_silent():
    h = server.Handler.__new__(server.Handler)
    h.log_message("%s", "msg")  # should not raise


def test_index_html_path(running_server):
    _, port, _ = running_server
    status, body = _get(port, "/index.html")
    assert status == 200
    assert "<html>" in body
