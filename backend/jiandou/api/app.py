"""FastAPI 应用入口 — 组装 routers、middleware、static files。

Usage:
    uv run jiandou serve start
    # or
    uvicorn jiandou.api.app:create_app --factory
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # Startup
    print("[JianDou] Starting up...")
    try:
        from jiandou.api.deps import get_task_queue
        queue = get_task_queue()
        await queue.start()
        print(f"[JianDou] Task queue started with {queue._max_workers} worker(s)")
    except Exception as e:
        print(f"[JianDou] Warning: task queue not started: {e}")

    yield

    # Shutdown
    print("[JianDou] Shutting down...")
    try:
        from jiandou.api.deps import get_task_queue
        queue = get_task_queue()
        await queue.stop(graceful=True)
        print("[JianDou] Task queue stopped")
    except Exception:
        pass


def create_app() -> FastAPI:
    """工厂函数 — 创建并配置 FastAPI 应用。"""

    app = FastAPI(
        title="JianDou Video",
        description="AI Video Generation API on Apple Silicon",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ── middleware ──
    from jiandou.api.middleware import setup_middleware

    config = _load_config()
    origins = config.server.cors_origins if config else ["*"]
    setup_middleware(app, origins)

    # ── routers ──
    from jiandou.api.routers import generate, tasks, models, system, ws, prompt

    app.include_router(generate.router)
    app.include_router(tasks.router)
    app.include_router(models.router)
    app.include_router(system.router)
    app.include_router(ws.router)
    app.include_router(prompt.router)

    # ── static files (Vue SPA) ──
    static_dir = _resolve_static_dir(config)
    if os.path.isdir(static_dir):
        from fastapi.responses import FileResponse

        index_html = os.path.join(static_dir, "index.html")

        if os.path.isfile(index_html):
            # Mount static assets at /assets
            assets_dir = os.path.join(static_dir, "assets")
            if os.path.isdir(assets_dir):
                app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

            # Favicon
            favicon = os.path.join(static_dir, "favicon.svg")
            if os.path.isfile(favicon):
                @app.get("/favicon.svg", include_in_schema=False)
                async def favicon_handler():
                    return FileResponse(favicon)

            # Serve SPA index.html for non-API routes via exception handler
            @app.middleware("http")
            async def spa_middleware(request, call_next):
                from fastapi.responses import JSONResponse
                response = await call_next(request)
                if response.status_code == 404:
                    path = request.url.path
                    if not path.startswith("/api/") and not path.startswith("/assets/"):
                        return FileResponse(index_html)
                    return JSONResponse({"detail": "Not Found"}, status_code=404)
                return response
    else:
        @app.get("/")
        async def root():
            return {"message": "JianDou Video API", "docs": "/api/docs"}

    return app


def _load_config():
    try:
        from jiandou.storage.config import load_config
        return load_config()
    except Exception:
        return None


def _resolve_static_dir(config) -> str:
    """Resolve Vue SPA dist directory."""
    if config:
        static_path = config.server.static_dir
        if os.path.isabs(static_path):
            return static_path
        # Relative to backend/
        return os.path.join(os.path.dirname(__file__), "..", "..", static_path)
    # Fallback
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "dist")


# ── direct run support ──

if __name__ == "__main__":
    import uvicorn

    config = _load_config()
    host = config.server.host if config else "0.0.0.0"
    port = config.server.port if config else 6701
    uvicorn.run("jiandou.api.app:create_app", host=host, port=port, factory=True)
