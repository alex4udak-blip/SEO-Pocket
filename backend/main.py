"""
SEO-Pocket Backend
Googlebot View - See pages as Google sees them
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
from contextlib import asynccontextmanager

from smart_fetcher import SmartFetcher
from parser import HTMLParser
from dataforseo import DataForSEOClient
from google_cache import GoogleCacheFetcher

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Global instances
fetcher: Optional[SmartFetcher] = None
dataforseo: Optional[DataForSEOClient] = None
google_cache: Optional[GoogleCacheFetcher] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage fetcher lifecycle"""
    global fetcher, dataforseo, google_cache

    print("=== Starting SmartFetcher ===")
    print(f"FLARESOLVERR_URL: {os.getenv('FLARESOLVERR_URL', 'NOT SET')}")
    print(f"PROXY_URL: {'SET' if os.getenv('PROXY_URL') else 'NOT SET'}")

    fetcher = SmartFetcher()
    await fetcher.start()

    print(f"=== SmartFetcher initialized ===")
    print(f"FlareSolverr available: {fetcher.flaresolverr_available}")
    print(f"Proxy URL configured: {bool(fetcher.proxy_url)}")

    # Initialize DataForSEO if configured
    dataforseo = DataForSEOClient()
    if dataforseo.is_configured():
        await dataforseo.start()

    # Initialize Google Cache fetcher
    google_cache = GoogleCacheFetcher()
    await google_cache.start()

    yield

    if fetcher:
        await fetcher.stop()
    if dataforseo:
        await dataforseo.stop()
    if google_cache:
        await google_cache.stop()


app = FastAPI(
    title="SEO-Pocket",
    description="View pages as Googlebot sees them",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


class AnalyzeRequest(BaseModel):
    url: HttpUrl


class AnalyzeResponse(BaseModel):
    success: bool
    url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    description: Optional[str] = None
    canonical: Optional[str] = None
    html_lang: Optional[str] = None
    hreflang: list[dict] = []
    robots: Optional[str] = None
    status_code: int = 200
    html: Optional[str] = None
    error: Optional[str] = None
    fetch_time_ms: int = 0
    # Fetch strategy info
    strategy: Optional[str] = None
    warning: Optional[str] = None
    # Google Cache indexed data
    site_indexed: bool = False
    indexed_title: Optional[str] = None
    indexed_description: Optional[str] = None
    indexed_h1: Optional[str] = None
    google_canonical: Optional[str] = None
    cache_date: Optional[str] = None
    indexed_html_lang: Optional[str] = None
    indexed_hreflang: list[dict] = []
    cache_html: Optional[str] = None
    # DataForSEO fallback (SERP data)
    serp_position: Optional[int] = None
    dataforseo_title: Optional[str] = None
    dataforseo_description: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_url(request: AnalyzeRequest):
    """Analyze URL as Googlebot sees it"""
    global fetcher, dataforseo, google_cache

    if not fetcher:
        raise HTTPException(status_code=503, detail="Fetcher not initialized")

    url = str(request.url)

    try:
        # Fetch page as Googlebot
        result = await fetcher.fetch(url)

        # Even if fetch failed, try to get cached/indexed data
        cache_data = {}
        dataforseo_data = {}

        if google_cache:
            cache_data = await google_cache.get_google_cache_data(url)

        if dataforseo and dataforseo.is_configured():
            dataforseo_data = await dataforseo.get_indexed_data(url)

        if not result["success"]:
            # Return error but include any available cached data
            site_indexed = cache_data.get("site_indexed", False) or dataforseo_data.get("indexed", False)
            return AnalyzeResponse(
                success=False,
                url=url,
                error=result.get("error", "Failed to fetch page"),
                fetch_time_ms=result.get("fetch_time_ms", 0),
                # Include cached data even on failure
                site_indexed=site_indexed,
                indexed_title=cache_data.get("indexed_title") or dataforseo_data.get("indexed_title"),
                indexed_description=cache_data.get("indexed_description") or dataforseo_data.get("indexed_description"),
                indexed_h1=cache_data.get("indexed_h1"),
                google_canonical=cache_data.get("google_canonical"),
                indexed_html_lang=cache_data.get("indexed_html_lang"),
                indexed_hreflang=cache_data.get("indexed_hreflang", []),
                cache_html=cache_data.get("cache_html"),
                cache_date=cache_data.get("cache_date"),
                dataforseo_title=dataforseo_data.get("indexed_title"),
                dataforseo_description=dataforseo_data.get("indexed_description"),
                serp_position=dataforseo_data.get("serp_position"),
                warning="Live fetch failed - showing cached/indexed data only" if site_indexed else None
            )

        # Parse HTML
        parser = HTMLParser(result["html"])
        parsed = parser.parse()

        # Determine if site is indexed (cache_data and dataforseo_data already fetched above)
        site_indexed = cache_data.get("site_indexed", False) or dataforseo_data.get("indexed", False)

        return AnalyzeResponse(
            success=True,
            url=url,
            title=parsed["title"],
            h1=parsed["h1"],
            description=parsed["description"],
            canonical=parsed["canonical"],
            html_lang=parsed["html_lang"],
            hreflang=parsed["hreflang"],
            robots=parsed["robots"],
            status_code=result.get("status_code", 200),
            html=result["html"],
            fetch_time_ms=result.get("fetch_time_ms", 0),
            # Fetch strategy info
            strategy=result.get("strategy"),
            warning=result.get("warning"),
            # Google Cache indexed data (primary)
            site_indexed=site_indexed,
            indexed_title=cache_data.get("indexed_title"),
            indexed_description=cache_data.get("indexed_description"),
            indexed_h1=cache_data.get("indexed_h1"),
            google_canonical=cache_data.get("google_canonical"),
            cache_date=cache_data.get("cache_date"),
            indexed_html_lang=cache_data.get("indexed_html_lang"),
            indexed_hreflang=cache_data.get("indexed_hreflang", []),
            cache_html=cache_data.get("cache_html"),
            # DataForSEO fallback
            serp_position=dataforseo_data.get("serp_position"),
            dataforseo_title=dataforseo_data.get("indexed_title"),
            dataforseo_description=dataforseo_data.get("indexed_description")
        )

    except Exception as e:
        return AnalyzeResponse(
            success=False,
            url=url,
            error=str(e)
        )


@app.get("/api/health")
async def health():
    """Health check with FlareSolverr status"""
    fs_status = "unknown"
    if fetcher and fetcher.flaresolverr:
        try:
            fs_status = "available" if await fetcher.flaresolverr.is_available() else "unavailable"
        except Exception as e:
            fs_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "fetcher": fetcher is not None,
        "flaresolverr_available": fetcher.flaresolverr_available if fetcher else False,
        "flaresolverr_status": fs_status,
        "flaresolverr_url": os.getenv("FLARESOLVERR_URL", "NOT SET"),
        "proxy_configured": bool(fetcher.proxy_url) if fetcher else False,
        "google_cache": google_cache is not None,
        "dataforseo": dataforseo is not None and dataforseo.is_configured()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
