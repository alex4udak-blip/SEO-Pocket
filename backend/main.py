"""
SEO-Pocket Backend
Googlebot View - See pages as Google sees them

New architecture inspired by affiliate.fm
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from core.logging import setup_logging, get_logger
from core.config import settings
from services.fetcher import SmartFetcher
from services.cache import HTMLCache
from services.dataforseo import DataForSEOClient
from services.wayback import WaybackClient
from api.routes import analyze_router, googlebot_router, health_router, googlebot_preview_router
from api.routes import analyze, googlebot, health, googlebot_preview

# Setup logging
setup_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Global service instances
fetcher: SmartFetcher = None
cache: HTMLCache = None
dataforseo: DataForSEOClient = None
wayback: WaybackClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle."""
    global fetcher, cache, dataforseo, wayback

    logger.info("=" * 50)
    logger.info("Starting SEO-Pocket Backend")
    logger.info("=" * 50)

    # Initialize cache
    cache = HTMLCache()
    await cache.start()
    logger.info(f"Cache initialized: {cache.cache_type}")

    # Initialize fetcher
    fetcher = SmartFetcher()
    await fetcher.start()
    logger.info(f"SmartFetcher initialized")
    logger.info(f"  - FlareSolverr: {'available' if fetcher.flaresolverr_available else 'not available'}")
    logger.info(f"  - Proxy: {'configured' if settings.proxy_url else 'not configured'}")

    # Initialize DataForSEO
    dataforseo = DataForSEOClient()
    if dataforseo.is_configured():
        await dataforseo.start()
        logger.info("DataForSEO client initialized")
    else:
        logger.warning("DataForSEO not configured (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)")

    # Initialize Wayback Machine client
    wayback = WaybackClient()
    await wayback.start()
    logger.info("Wayback Machine client initialized")

    # Inject dependencies into routes
    analyze.set_dependencies(fetcher, cache, dataforseo, wayback)
    googlebot.set_dependencies(fetcher, cache)
    health.set_dependencies(fetcher, cache, dataforseo)
    googlebot_preview.set_dependencies(fetcher, cache)

    logger.info("=" * 50)
    logger.info("SEO-Pocket Backend ready!")
    logger.info("=" * 50)

    yield

    # Cleanup
    logger.info("Shutting down...")
    if fetcher:
        await fetcher.stop()
    if cache:
        await cache.stop()
    if dataforseo:
        await dataforseo.stop()
    if wayback:
        await wayback.stop()


app = FastAPI(
    title="SEO-Pocket",
    description="View pages as Googlebot sees them - with cloaking detection",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(analyze_router, prefix="/api")
app.include_router(googlebot_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(googlebot_preview_router, prefix="/api")


# Static files and frontend
@app.get("/")
async def root():
    """Serve frontend."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "SEO-Pocket API", "docs": "/docs"}


# Mount static files if directory exists
if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
