"""
FastAPI Application Entry Point for TAIKRY AI MARKET INTELLIGENCE PRO
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi.responses import RedirectResponse

from taikry.config import APP_NAME, APP_VERSION
from taikry.database.session import init_db
from taikry.api.routes import router as api_router
from taikry.monitoring.engine import market_monitor_247

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database tables
    init_db()
    # Start 24/7 autonomous monitoring thread in background by default
    auto_monitor = os.getenv("AUTO_START_MONITORING", "true").lower() in ("true", "1", "yes")
    if auto_monitor:
        market_monitor_247.start_background()
    yield
    # Shutdown
    market_monitor_247.stop()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Institutional-grade, autonomous 24/7 AI financial market intelligence platform for Gold, Forex, and Crypto.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root redirect to Web Dashboard for seamless browser access
@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/dashboard/", status_code=307)

# Fast keep-alive ping for cloud free tier monitors (e.g. UptimeRobot, Cron-Job)
@app.get("/ping", tags=["System"])
def ping():
    return {"status": "pong", "app": APP_NAME, "version": APP_VERSION}

# Include API routes
app.include_router(api_router)

# Mount web dashboard if directory exists
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/dashboard", StaticFiles(directory=web_dir, html=True), name="dashboard")
