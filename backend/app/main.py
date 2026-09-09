from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request
from fastapi import HTTPException as FastAPIHTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.limiter import limiter


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

# In-memory, per-process rate limiting (fine for the single Render instance
# this runs on today; swap the storage_uri for a Redis-backed one if/when
# the backend scales to multiple instances). Applied to the AI and upload
# routes only - see their `@limiter.limit(...)` decorators - so normal
# farmer usage (a handful of Flock Checks a day) is never throttled.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


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
# CORS_ORIGINS (see app/core/config.py) is the source of truth for the
# allowed frontend origin(s) in production - typically the Vercel deployment
# URL(s) - configured via the CORS_ORIGINS env var, not hard-coded here.
allow_origins = list(settings.cors_origins)
if settings.environment.lower() == "development":
    # Wildcard only in the explicit local-dev case.
    allow_origins = ["*"]
    _logger.info("ENVIRONMENT=development - CORS is wide open for local dev use.")
else:
    # Fail closed for production AND for any unrecognized/misconfigured
    # ENVIRONMENT value (e.g. a typo'd "prod") - only the configured
    # CORS_ORIGINS (plus the app's own public URL) are ever allowed.
    if settings.app_public_url and settings.app_public_url not in allow_origins:
        allow_origins.append(settings.app_public_url)
    if not allow_origins:
        _logger.warning(
            "ENVIRONMENT=%s but CORS_ORIGINS is empty - set it to the deployed "
            "frontend URL(s) (e.g. the Vercel deployment URL) or the frontend won't "
            "be able to call this API.",
            settings.environment,
        )
    if not settings.is_production:
        _logger.warning(
            "ENVIRONMENT=%s is neither 'development' nor 'production' - treating it "
            "as production-like (restrictive CORS). Set ENVIRONMENT=production explicitly on Render.",
            settings.environment,
        )

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
