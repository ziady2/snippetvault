"""Tiny HTTP server.

Stdlib only. Localhost only. The server reads the book on every
request — no caching — because I rather not deal with invalidation.

This module exposes one ``serve`` function plus the ``Handler`` class
so it can be tested with ``http.server`` test fixtures.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

from . import io_html
from .errors import BookNotFoundError
from .storage import Book


def _book_for_request(book_path: Path) -> Optional[Book]:
    try:
        return Book.load(book_path)
    except BookNotFoundError:
        return None


class Handler(BaseHTTPRequestHandler):
    book_path: Path = Path()  # set per server

    def do_GET(self) -> None:  # noqa: N802  # stdlib name
        # the kitchen tablet is annoying about CORS
        path = self.path.split("?", 1)[0]
        book = _book_for_request(self.book_path)
        if book is None:
            return self._send(404, "text/plain", "no book at " + str(self.book_path))
        if path in ("/", "/index", "/index.html"):
            html = io_html.render(list(book), title="snippetbox")
            return self._send(200, "text/html; charset=utf-8", html)
        if path == "/api/snippets":
            payload = [s.to_dict() for s in book]
            return self._send(200, "application/json", json.dumps(payload, ensure_ascii=False))
        if path.startswith("/api/snippet/"):
            sid = path[len("/api/snippet/") :]
            s = book.get(sid)
            if s is None:
                return self._send(404, "application/json", json.dumps({"error": "not found"}))
            return self._send(200, "application/json", json.dumps(s.to_dict(), ensure_ascii=False))
        if path.startswith("/snippet/"):
            slug = path[len("/snippet/") :]
            s = book.get_by_slug(slug)
            if s is None:
                return self._send(404, "text/plain", "not found")
            return self._send(200, "text/html; charset=utf-8", io_html.render([s], title=s.title or slug))
        if path == "/healthz":
            return self._send(200, "text/plain", "ok\n")
        return self._send(404, "text/plain", "not found")

    def log_message(self, format, *args) -> None:  # noqa: A003
        # silence the default per-request logging; the CLI shows
        # only what we want it to show.
        return

    def _send(self, status: int, content_type: str, body) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(book_path: Path, host: str = "127.0.0.1", port: int = 8765) -> HTTPServer:
    """Construct an ``HTTPServer`` bound to host/port. Caller starts/stops it."""
    handler_class = type(
        "BoundHandler",
        (Handler,),
        {"book_path": Path(book_path)},
    )
    server = HTTPServer((host, int(port)), handler_class)
    return server


def serve(book_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:  # pragma: no cover
    """Run forever. CLI uses this; tests use ``make_server``."""
    server = make_server(book_path, host=host, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def reachable(host: str, port: int, *, timeout: float = 0.5) -> bool:
    """Helper used in tests to check if a port is open."""
    import socket as _s

    sock = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
    except OSError:
        return False
    finally:
        sock.close()
    return True
