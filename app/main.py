"""
TalentScout — FastAPI application entry point.

Responsibilities:
- Create FastAPI app instance with metadata
- Configure CORS
- Mount API router
- Create DB tables on startup (dev-friendly)
- Configure structured logging
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(pathname)s:%(lineno)d | %(message)s",
)
logger = logging.getLogger(__name__)


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "AI-powered hiring assistant that collects candidate profiles "
            "and generates personalised technical interview questions."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(router, prefix="/api/v1")

    # ── Startup: create tables ────────────────────────────────────────────────
    @app.on_event("startup")
    def on_startup() -> None:
        """Create all DB tables if they do not exist (dev convenience)."""
        logger.info("Creating database tables if not present…")
        # Import models so Base.metadata knows about them
        from app.models import candidate  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("Database ready.")

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        logger.info("TalentScout shutting down.")

    return app


app = create_app()
