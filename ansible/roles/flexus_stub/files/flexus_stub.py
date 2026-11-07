#!/usr/bin/env python3
"""Fake Klipsch Flexus soundbar for the Molecule harness (test-only, stdlib only).

Serves exactly what custom_components/klipsch_flexus calls on a real soundbar:

* port 80   ``GET  /api/getData?path=<p>&roles=<value|edit>``  -> JSON list
            ``GET  /api/getRows?path=<p>&roles=@all&...``       -> {"rows": [...]}
            ``POST /api/setData`` JSON {"path", "roles", "value"} -> 200 (authMode "none")
            ``GET  /api/setData?...`` -> 405 "Strict HTTP required!" (2026 firmware)
* port 8008 ``GET  /setup/eureka_info`` (Google Cast API)

Values come from a NON-SECRET fixture (fixture.json, documentation MAC 02:00:00:00:00:01). A
``setData`` changes the served value, as on the device, and is appended to the writes file
(JSON lines) so the verify step can assert which writes reached the "device". A read of a path
the fixture does not know is answered 404 and appended to the unknown-paths file, so a harness
that drifts from the integration's protocol is visible instead of silently passing.

Usage: flexus_stub.py --fixture FILE --state-dir DIR --bind ADDR [--bind ADDR ...]
"""

from __future__ import annotations

import argparse
import copy
import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

API_PORT = 80
CAST_PORT = 8008


class Device:
    """The soundbar's state: fixture values, mutated by writes, guarded by one lock."""

    def __init__(self, fixture: dict, state_dir: Path) -> None:
        self._lock = threading.Lock()
        self.values: dict[str, list] = copy.deepcopy(fixture["values"])
        self.edit: dict[str, list] = copy.deepcopy(fixture.get("edit", {}))
        self.rows: dict[str, dict] = copy.deepcopy(fixture.get("rows", {}))
        self.eureka: dict = copy.deepcopy(fixture["eureka_info"])
        self.writes_file = state_dir / "writes.jsonl"
        self.unknown_file = state_dir / "unknown_paths.jsonl"
        self.requests_file = state_dir / "requests.jsonl"

    @staticmethod
    def _append(path: Path, record: dict) -> None:
        record = {"ts": round(time.time(), 3), **record}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def log_request(self, method: str, path: str, query: str) -> None:
        with self._lock:
            self._append(self.requests_file, {"method": method, "path": path, "query": query})

    def get_data(self, path: str, roles: str) -> list | None:
        with self._lock:
            source = self.edit if roles == "edit" else self.values
            value = source.get(path)
            if value is None:
                self._append(self.unknown_file, {"api": "getData", "path": path, "roles": roles})
                return None
            return copy.deepcopy(value)

    def get_rows(self, path: str) -> dict | None:
        with self._lock:
            rows = self.rows.get(path)
            if rows is None:
                self._append(self.unknown_file, {"api": "getRows", "path": path})
                return None
            return copy.deepcopy(rows)

    def set_data(self, path: str, roles: str, value: object) -> tuple[int, str]:
        with self._lock:
            known = path in self.values or path in ("powermanager:targetRequest", "player:player/control")
            self._append(self.writes_file, {"path": path, "roles": roles, "value": value, "known": known})
            if not known:
                return 404, json.dumps({"error": f"unknown path {path}"})
            if roles == "value" and isinstance(value, dict):
                self.values[path] = [value]
            elif path == "powermanager:targetRequest" and isinstance(value, dict) and value.get("target"):
                self.values["powermanager:target"] = [
                    {"type": "powerTarget", "powerTarget": {"target": value["target"], "reason": "userActivity"}}
                ]
            return 200, "true"


class StubServer(ThreadingHTTPServer):
    """HTTP server without HTTPServer's reverse-DNS lookup of the bind address.

    ``HTTPServer.server_bind`` calls ``socket.getfqdn``, which waits for DNS timeouts in a
    container without a resolver (the scenarios run on an internal network).
    """

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port


def make_handler(device: Device, port: int) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "FlexusStub/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: object) -> None:  # noqa: D102 - keep stderr quiet
            return

        def _send(self, status: int, body: str, content_type: str = "application/json") -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            device.log_request("GET", url.path, url.query)
            if port == CAST_PORT:
                if url.path == "/setup/eureka_info":
                    self._send(200, json.dumps(device.eureka))
                else:
                    self._send(404, "{}")
                return
            path = query.get("path", [""])[0]
            if url.path == "/api/getData":
                value = device.get_data(path, query.get("roles", ["value"])[0])
                if value is None:
                    self._send(404, json.dumps({"error": f"unknown path {path}"}))
                else:
                    self._send(200, json.dumps(value))
            elif url.path == "/api/getRows":
                rows = device.get_rows(path)
                if rows is None:
                    self._send(404, json.dumps({"error": f"unknown path {path}"}))
                else:
                    self._send(200, json.dumps(rows))
            elif url.path == "/api/setData":
                # 2026 firmware answers the legacy GET write like this.
                self._send(405, "Strict HTTP required!", "text/plain")
            else:
                self._send(404, "{}")

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            url = urlsplit(self.path)
            device.log_request("POST", url.path, url.query)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if port != API_PORT or url.path != "/api/setData":
                self._send(404, "{}")
                return
            try:
                body = json.loads(raw or b"{}")
                path, roles, value = body["path"], body.get("roles", "value"), body["value"]
            except (ValueError, KeyError, TypeError):
                self._send(400, json.dumps({"error": "bad setData body"}))
                return
            status, text = device.set_data(path, roles, value)
            self._send(status, text)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--bind", action="append", required=True, help="address to listen on (repeatable)")
    args = parser.parse_args()

    args.state_dir.mkdir(parents=True, exist_ok=True)
    device = Device(json.loads(args.fixture.read_text(encoding="utf-8")), args.state_dir)
    servers = [
        StubServer((address, port), make_handler(device, port))
        for address in args.bind
        for port in (API_PORT, CAST_PORT)
    ]
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"flexus stub listening on {', '.join(args.bind)} ports {API_PORT}/{CAST_PORT}", flush=True)
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
