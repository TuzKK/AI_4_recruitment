"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from database.db import init_db
from web.routes import chat, browser_extension, boss_accounts, candidates, dashboard, market_research, positions, settings, tasks, websocket


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith(('api/', 'assets/')) and '.' not in path:
                return await super().get_response('index.html', scope)
            raise


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Boss 直聘自动化招聘系统",
        version="1.0.0",
        description="Automated recruitment system powered by RPA + LLM",
    )

    # CORS – allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(chat.router)
    app.include_router(positions.router)
    app.include_router(tasks.router)
    app.include_router(candidates.router)
    app.include_router(dashboard.router)
    app.include_router(settings.router)
    app.include_router(boss_accounts.router)
    app.include_router(browser_extension.router)
    app.include_router(market_research.router)
    app.include_router(websocket.router)

    @app.get("/api/health")
    def health_check():
        return {"status": "ok"}

    # Serve frontend build last so it does not shadow API routes.
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", SPAStaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    # Initialize database on startup
    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        from database.db import SessionLocal
        from database.models import BrowserChatSend
        with SessionLocal() as db:
            db.query(BrowserChatSend).filter_by(status='sending').update({'status':'unknown','detail':'服务中断，结果未知，请在 BOSS 核对；不会自动重发'})
            db.commit()

    return app
