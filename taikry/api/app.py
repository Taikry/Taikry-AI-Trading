"""
FastAPI Application Entry Point for TAIKRY AI MARKET INTELLIGENCE PRO
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse

from taikry.config import APP_NAME, APP_VERSION, CORS_ALLOWED_ORIGINS, PUBLIC_APP_URL
from taikry.database.session import init_db, SessionLocal
from taikry.api.routes import router as api_router
from taikry.api.saas_routes import saas_router
from taikry.api.schema_routes import schema_router
from taikry.monitoring.engine import market_monitor_247

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database tables
    init_db()

    # Initialize SaaS default subscription plans and bootstrap admin if needed
    try:
        from taikry.saas.entitlement_service import init_default_plans
        from taikry.saas.admin_service import bootstrap_admin_if_needed
        db_startup = SessionLocal()
        try:
            init_default_plans(db_startup)
            bootstrap_admin_if_needed(db_startup)
        finally:
            db_startup.close()
    except Exception as err:
        import logging
        logging.getLogger("uvicorn.error").warning(f"SaaS bootstrap notice: {err}")

    # Start the monitoring thread in this process when enabled.
    auto_monitor = os.getenv("AUTO_START_MONITORING", "true").lower() in ("true", "1", "yes")
    if auto_monitor:
        market_monitor_247.start_background()
    yield
    # Shutdown
    market_monitor_247.stop()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Market analysis and paper-trading monitor for Gold, Forex, and Crypto. Availability depends on configured providers, market data, and host uptime.",
    lifespan=lifespan
)

cors_origins = [origin.strip().rstrip("/") for origin in CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]
for public_origin in (PUBLIC_APP_URL, os.getenv("RENDER_EXTERNAL_URL", "")):
    public_origin = public_origin.strip().rstrip("/")
    if public_origin and public_origin not in cors_origins:
        cors_origins.append(public_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root landing page for ZYROX AI SaaS Platform
@app.get("/", include_in_schema=False)
def root_page():
    landing_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "landing.html")
    if os.path.exists(landing_file):
        return FileResponse(landing_file)
    return RedirectResponse(url="/dashboard/", status_code=307)

# Fast keep-alive ping for cloud free tier monitors (e.g. UptimeRobot, Cron-Job)
@app.get("/ping", tags=["System"])
def ping():
    return {"status": "pong", "app": APP_NAME, "version": APP_VERSION}

# Include API routes
app.include_router(api_router)
app.include_router(saas_router)
app.include_router(schema_router)

# Mount web dashboard if directory exists
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/dashboard", StaticFiles(directory=web_dir, html=True), name="dashboard")

