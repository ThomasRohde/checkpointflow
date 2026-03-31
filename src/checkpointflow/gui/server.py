"""Starlette web server for the checkpointflow GUI."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from checkpointflow.gui.api import (
    bulk_delete_runs,
    delete_run,
    discover_workflows,
    get_run_detail,
    get_step_output,
    list_runs,
    parse_workflow,
)
from checkpointflow.persistence.store import Store

STATIC_DIR = Path(__file__).parent / "static"


def _json(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def create_app(base_dir: Path | None = None) -> Starlette:
    """Create the Starlette ASGI app."""
    resolved_base = base_dir or Path.home() / ".checkpointflow"
    store = Store(base_dir=resolved_base)

    async def api_runs(request: Request) -> Response:
        return _json(list_runs(store))

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

    return Starlette(routes=routes)


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
