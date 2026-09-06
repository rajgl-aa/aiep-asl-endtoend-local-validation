import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_app_settings
from app.core.otel_logger import configure_logger, get_logger
from app.status.routers import status_router

# Use the cached singleton so all modules share one AppSettings instance
app_settings = get_app_settings()

app = FastAPI(
    title=app_settings.app_title,
    description=app_settings.app_description,
    version=app_settings.app_version,
)

configure_logger()
logger = get_logger(__name__)

# Log application startup
logger.info("🚀 FastAPI application initialized",
            app_title=app.title,
            version=app.version,
            cors_origins=app_settings.get_cors_origins_list())

# Configure CORS with environment-driven origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.get_cors_origins_list(),
    allow_credentials=app_settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation ID middleware for request tracing
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to all requests for tracing across logs."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.get("/")
async def docs_reroute() -> RedirectResponse:
    return RedirectResponse(url="/docs")


# This is how to include routers
app.include_router(status_router.router, prefix="/api/v1", tags=["status"])

# Log startup completion
logger.info("✅ FastAPI application ready",
            endpoints={"status": "/api/v1/status", "docs": "/docs"})
