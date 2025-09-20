from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .logging_config import configure_logging, logger
from .models import RootResponse
from .routes import api_router
from .services import get_important_email_watcher, get_trigger_scheduler


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.debug("validation error", extra={"errors": exc.errors(), "path": str(request.url)})
        return JSONResponse(
            {"ok": False, "error": "Invalid request", "detail": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException):
        logger.debug(
            "http error",
            extra={"detail": exc.detail, "status": exc.status_code, "path": str(request.url)},
        )
        detail: Any = exc.detail
        if not isinstance(detail, str):
            detail = json.dumps(detail)
        return JSONResponse({"ok": False, "error": detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error", extra={"path": str(request.url)})
        return JSONResponse(
            {"ok": False, "error": "Internal server error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


configure_logging()
_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    docs_url=_settings.resolved_docs_url,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


def _public_endpoints(request: Request) -> list[str]:
    return sorted(
        {
            route.path
            for route in request.app.routes
            if getattr(route, "include_in_schema", False) and route.path.startswith("/api/")
        }
    )


@app.get("/")
def root(request: Request, settings: Settings = Depends(get_settings)) -> RootResponse:
    return RootResponse(
        status="ok",
        service="openpoke",
        version=settings.app_version,
        endpoints=_public_endpoints(request),
    )


@app.on_event("startup")
async def _start_trigger_scheduler() -> None:
    scheduler = get_trigger_scheduler()
    await scheduler.start()
    watcher = get_important_email_watcher()
    await watcher.start()


@app.on_event("shutdown")
async def _stop_trigger_scheduler() -> None:
    scheduler = get_trigger_scheduler()
    await scheduler.stop()
    watcher = get_important_email_watcher()
    await watcher.stop()


__all__ = ["app"]
