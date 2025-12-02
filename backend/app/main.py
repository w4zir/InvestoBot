from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .routes import health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FastAPI Starter",
    description="A minimal FastAPI starter with authentication",
    version="1.0.0"
)

# CORS for local dev; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["Health"]) 


