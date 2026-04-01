from __future__ import annotations

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

import pytest

from checkpointflow.engine.steps.api_step import execute
from checkpointflow.models.state import RunContext
from checkpointflow.models.workflow import ApiStep


class _TestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/ok":
            body = json.dumps({"status": "ok", "value": 42}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/text":
            body = b"plain text response"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/error":
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body_bytes = self.rfile.read(length) if length > 0 else b""
        # Echo back the request body
        response = json.dumps({"received": json.loads(body_bytes.decode()) if body_bytes else None})
        resp_bytes = response.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress logging


@pytest.fixture()
def test_server(monkeypatch: pytest.MonkeyPatch) -> Any:
    # Bypass SSRF protection for integration tests against localhost
    monkeypatch.setattr("checkpointflow.engine.steps.api_step._is_blocked_host", lambda _: False)
    server = HTTPServer(("127.0.0.1", 0), _TestHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_api_get_json_response(run_ctx: Callable[..., RunContext], test_server: str) -> None:
    step = ApiStep.model_validate(
        {
            "id": "fetch",
            "kind": "api",
            "method": "GET",
            "url": f"{test_server}/ok",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["status"] == "ok"
    assert result.outputs["value"] == 42


def test_api_get_text_response(run_ctx: Callable[..., RunContext], test_server: str) -> None:
    step = ApiStep.model_validate(
        {
            "id": "fetch",
            "kind": "api",
            "method": "GET",
            "url": f"{test_server}/text",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["body"] == "plain text response"


def test_api_post_with_body(run_ctx: Callable[..., RunContext], test_server: str) -> None:
    step = ApiStep.model_validate(
        {
            "id": "send",
            "kind": "api",
            "method": "POST",
            "url": f"{test_server}/",
            "body": {"key": "value"},
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["received"] == {"key": "value"}


def test_api_server_error_fails(run_ctx: Callable[..., RunContext], test_server: str) -> None:
    step = ApiStep.model_validate(
        {
            "id": "fail",
            "kind": "api",
            "method": "GET",
            "url": f"{test_server}/error",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False


def test_api_custom_success_codes(run_ctx: Callable[..., RunContext], test_server: str) -> None:
    step = ApiStep.model_validate(
        {
            "id": "ok500",
            "kind": "api",
            "method": "GET",
            "url": f"{test_server}/error",
            "success": {"status_codes": [500]},
        }
    )
    result = execute(step, run_ctx())
    assert result.success is True


def test_api_url_interpolation(run_ctx: Callable[..., RunContext], test_server: str) -> None:
    step = ApiStep.model_validate(
        {
            "id": "fetch",
            "kind": "api",
            "method": "GET",
            "url": "${inputs.base_url}/ok",
        }
    )
    result = execute(step, run_ctx(inputs={"base_url": test_server}))
    assert result.success is True
    assert result.outputs is not None
    assert result.outputs["status"] == "ok"


def test_api_connection_error(
    run_ctx: Callable[..., RunContext], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("checkpointflow.engine.steps.api_step._is_blocked_host", lambda _: False)
    step = ApiStep.model_validate(
        {
            "id": "fail",
            "kind": "api",
            "method": "GET",
            "url": "http://127.0.0.1:1/nonexistent",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert result.error_message is not None


# --- URL scheme validation ---


def test_api_rejects_file_scheme(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {"id": "bad", "kind": "api", "method": "GET", "url": "file:///etc/passwd"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "scheme" in (result.error_message or "").lower()


def test_api_rejects_gopher_scheme(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {"id": "bad", "kind": "api", "method": "GET", "url": "gopher://evil.com"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "scheme" in (result.error_message or "").lower()


def test_api_rejects_data_scheme(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {"id": "bad", "kind": "api", "method": "GET", "url": "data:text/html,hello"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "scheme" in (result.error_message or "").lower()


# --- Header interpolation errors ---


def test_api_header_interpolation_failure(
    run_ctx: Callable[..., RunContext], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("checkpointflow.engine.steps.api_step._is_blocked_host", lambda _: False)
    step = ApiStep.model_validate(
        {
            "id": "hdr",
            "kind": "api",
            "method": "GET",
            "url": "http://localhost:1/test",
            "headers": {"Authorization": "Bearer ${nonexistent.token}"},
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "header" in (result.error_message or "").lower()
    assert "Authorization" in (result.error_message or "")


# --- SSRF protection ---


def test_api_blocks_metadata_endpoint(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {
            "id": "ssrf",
            "kind": "api",
            "method": "GET",
            "url": "http://169.254.169.254/latest/meta-data/",
        }
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "blocked" in (result.error_message or "").lower()


def test_api_blocks_loopback_address(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {"id": "ssrf", "kind": "api", "method": "GET", "url": "http://127.0.0.1/test"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "blocked" in (result.error_message or "").lower()


def test_api_blocks_private_address(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {"id": "ssrf", "kind": "api", "method": "GET", "url": "http://10.0.0.1/test"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "blocked" in (result.error_message or "").lower()


def test_api_blocks_reserved_address(run_ctx: Callable[..., RunContext]) -> None:
    step = ApiStep.model_validate(
        {"id": "ssrf", "kind": "api", "method": "GET", "url": "http://0.0.0.0/test"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "blocked" in (result.error_message or "").lower()


def test_api_dns_failure_blocks_request(
    run_ctx: Callable[..., RunContext], monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket as _socket

    monkeypatch.setattr(
        "checkpointflow.engine.steps.api_step.socket.gethostbyname",
        lambda _: (_ for _ in ()).throw(_socket.gaierror("DNS failed")),
    )
    step = ApiStep.model_validate(
        {"id": "ssrf", "kind": "api", "method": "GET", "url": "http://will-not-resolve.invalid/"}
    )
    result = execute(step, run_ctx())
    assert result.success is False
    assert "blocked" in (result.error_message or "").lower()
