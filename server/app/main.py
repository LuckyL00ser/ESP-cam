from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.api.captures import router as captures_router
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.stats import router as stats_router
from app.api.uploads import router as uploads_router
from app.config import get_settings
from app.database import create_db, get_engine, get_session
from app.services.cleanup_service import CleanupService
from app.services.migration_service import MigrationService
from app.services.stats_service import StatsService

STATIC_DIR = Path(__file__).resolve().parent / "static"


async def cleanup_loop() -> None:
    settings = get_settings()
    while True:
        with Session(get_engine()) as session:
            CleanupService(session).cleanup_old_captures()
        await asyncio.sleep(settings.capture_cleanup_interval_seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db()
    with Session(get_engine()) as session:
        MigrationService(session).import_jsonl_if_needed()
        CleanupService(session).cleanup_old_captures()

    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="esp-cam upload server", version="0.2.0", lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(health_router)
    app.include_router(uploads_router)
    app.include_router(history_router)
    app.include_router(captures_router)
    app.include_router(stats_router)

    @app.get("/")
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/latency")
    def latency_alias() -> dict:
        with Session(get_engine()) as session:
            return StatsService(session).legacy_latency_payload()

    return app


app = create_app()
