"""Starlette web server for the checkpointflow GUI."""

from __future__ import annotations

import webbrowser
from collections.abc import AsyncGenerator, MutableMapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from checkpointflow.gui.api import (
    bulk_delete_runs,
    count_runs,
    delete_run,
    discover_workflows,
    get_run_detail,
    get_step_output,
    list_runs,
    parse_workflow,
)
from checkpointflow.persistence.store import Store

STATIC_DIR = Path(__file__).parent / "static"

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    ),
]


class SecurityHeadersMiddleware:
    """Add security headers to all HTTP responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_SECURITY_HEADERS)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class CORSMiddleware:
    """Restrict cross-origin requests to localhost origins only."""

    _ALLOWED_ORIGIN_PREFIX = b"http://localhost"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _is_allowed_origin(origin: bytes) -> bool:
        prefix = CORSMiddleware._ALLOWED_ORIGIN_PREFIX
        if not origin.startswith(prefix):
            return False
        rest = origin[len(prefix) :]
        return rest == b"" or rest[:1] in (b":", b"/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"")

        if not self._is_allowed_origin(origin):
            # No CORS headers for non-localhost origins
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "")
        if method == "OPTIONS":
            # Preflight response
            await send(
                {
                    "type": "http.response.start",
                    "status": 204,
                    "headers": [
                        (b"access-control-allow-origin", origin),
                        (b"access-control-allow-methods", b"GET, POST, DELETE, OPTIONS"),
                        (b"access-control-allow-headers", b"authorization, content-type"),
                        (b"access-control-max-age", b"3600"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_cors(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                msg_headers.append((b"access-control-allow-origin", origin))
                message["headers"] = msg_headers
            await send(message)

        await self.app(scope, receive, send_with_cors)


def _json(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def create_app(base_dir: Path | None = None) -> Starlette:
    """Create the Starlette ASGI app."""
    resolved_base = base_dir or Path.home() / ".checkpointflow"
    store = Store(base_dir=resolved_base)

    async def api_runs(request: Request) -> Response:
        page = int(request.query_params.get("page", "1"))
        per_page = int(request.query_params.get("per_page", "50"))
        page = max(1, page)
        per_page = max(1, min(per_page, 200))
        offset = (page - 1) * per_page
        runs = list_runs(store, limit=per_page, offset=offset)
        total = count_runs(store)
        return _json({"runs": runs, "total": total, "page": page, "per_page": per_page})

    async def api_run_detail(request: Request) -> Response:
        run_id = request.path_params["run_id"]
        detail = get_run_detail(store, run_id)
        if detail is None:
            return _json({"error": "Run not found"}, 404)
        return _json(detail)

    async def api_delete_run(request: Request) -> Response:
        from checkpointflow.persistence.store import PersistenceError

        run_id = request.path_params["run_id"]
        try:
            result = delete_run(store, run_id)
        except PersistenceError:
            return _json({"error": "Cannot delete active run"}, 409)
        if result is None:
            return _json({"error": "Run not found"}, 404)
        return _json(result)

    async def api_bulk_delete(request: Request) -> Response:
        body = await request.json()
        run_ids: list[str] = body.get("run_ids", [])
        result = bulk_delete_runs(store, run_ids)
        return _json(result)

    async def api_step_stream(request: Request) -> Response:
        run_id = request.path_params["run_id"]
        step_id = request.path_params["step_id"]
        stream = request.path_params["stream"]
        if stream not in ("stdout", "stderr"):
            return _json({"error": "Invalid stream"}, 400)
        content = get_step_output(store, run_id, step_id, stream)
        if content is None:
            return _json({"error": "Not found"}, 404)
        return PlainTextResponse(content)

    allowed_dirs = [Path.cwd() / ".checkpointflow", resolved_base]

    async def api_workflows(request: Request) -> Response:
        path = request.query_params.get("path")
        if path:
            resolved = Path(path).resolve()
            if not any(resolved.is_relative_to(d.resolve()) for d in allowed_dirs if d.is_dir()):
                return _json({"error": "Path not in allowed workflow directories"}, 403)
            parsed = parse_workflow(str(resolved))
            if parsed is None:
                return _json({"error": "Could not parse workflow"}, 404)
            return _json(parsed)
        return _json(discover_workflows(resolved_base))

    async def spa_fallback(request: Request) -> Response:
        index = STATIC_DIR / "index.html"
        if index.exists():
            return Response(
                content=index.read_text(encoding="utf-8"),
                media_type="text/html",
            )
        return PlainTextResponse(
            "GUI not built. Run: cd gui && npm install && npm run build",
            status_code=503,
        )

    routes: list[Route | Mount] = [
        Route("/api/runs", api_runs),
        Route("/api/runs/{run_id}", api_run_detail),
        Route("/api/runs/{run_id}", api_delete_run, methods=["DELETE"]),
        Route("/api/runs/bulk-delete", api_bulk_delete, methods=["POST"]),
        Route("/api/runs/{run_id}/steps/{step_id}/{stream}", api_step_stream),
        Route("/api/workflows", api_workflows),
    ]

    # Serve static assets if they exist
    if (STATIC_DIR / "assets").exists():
        routes.append(Mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets"))

    # SPA fallback for all other routes
    routes.append(Route("/{path:path}", spa_fallback))

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncGenerator[None]:
        yield
        store.close()

    inner = Starlette(routes=routes, lifespan=lifespan)
    return SecurityHeadersMiddleware(CORSMiddleware(inner))  # type: ignore[return-value]


def run_server(port: int = 8420, base_dir: Path | None = None) -> None:
    """Start the GUI server."""
    import signal
    import sys

    import uvicorn

    # On Windows, reset SIGINT to default so Ctrl-C actually terminates the process.
    if sys.platform == "win32":
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = create_app(base_dir=base_dir)
    url = f"http://localhost:{port}"
    print(f"checkpointflow dashboard: {url}")
    webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
