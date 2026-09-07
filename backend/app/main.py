from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
)
from app.core.config import settings

app = FastAPI(title="FlockGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
