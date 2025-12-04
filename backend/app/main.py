import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.logging import configure_logging, get_logger
from .routes import control, data, health, status, strategies

# Configure structured logging with JSON format and file persistence
settings = get_settings()
configure_logging(
    level=logging.INFO,
    enable_json=True,
    enable_file=True,
)
logger = get_logger(__name__)

app = FastAPI(
    title="InvestoBot Orchestrator",
    description="Autonomous trading orchestrator with Google Agents, backtesting, and Alpaca paper trading.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # In production you should restrict allowed origins.
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
app.include_router(status.router, prefix="/trading", tags=["Trading Status"])
app.include_router(control.router, prefix="/control", tags=["Control"])
app.include_router(data.router, prefix="/data", tags=["Data Management"])


@app.get("/status")
async def root_status():
    """
    Lightweight status endpoint giving basic environment information.
    """
    return {
        "app": "InvestoBot Orchestrator",
        "environment": settings.env,
        "debug": settings.debug,
    }




