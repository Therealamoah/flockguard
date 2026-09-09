from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request
from fastapi import HTTPException as FastAPIHTTPException


_logger = logging.getLogger(__name__)

from app.api.routes import (
    alerts,
    analytics,
    ask,
    farms,
    flock_checks,
    flocks,
    health,
    houses,
    inspections,
    media,
    debug,
)
from app.core.config import settings

app = FastAPI(title="FlockGuard API")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
        text = body.decode("utf-8", errors="replace")
    except Exception:
        text = "<unavailable>"
    _logger.warning(
        "Request validation error: %s path=%s body=%s",
        exc.errors(),
        request.url.path,
        (text[:1000] + "...") if len(text) > 1000 else text,
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(FastAPIHTTPException)
async def http_exception_logger(request: Request, exc: FastAPIHTTPException):
    _logger.warning("HTTP error: status=%s path=%s detail=%s", exc.status_code, request.url.path, getattr(exc, "detail", ""))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    _logger.exception("Unhandled exception while handling request %s: %s", request.url.path, str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Ensure the deployed front-end URL is allowed and make development more
# convenient by permitting all origins when running in development.
allow_origins = list(settings.cors_origins)
if settings.environment == "development":
    allow_origins = ["*"]
else:
    if settings.app_public_url and settings.app_public_url not in allow_origins:
        allow_origins.append(settings.app_public_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(farms.router)
app.include_router(houses.router)
app.include_router(flocks.router)
app.include_router(flock_checks.router)
app.include_router(inspections.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(ask.router)
app.include_router(media.router)
app.include_router(debug.router)
