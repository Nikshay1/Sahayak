"""
Sahayak Main Application
Zero-UI Agentic AI for Elderly Medicine Ordering
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from src.config.settings import settings
from src.db.database import engine, Base
from src.api.routes import voice, wallet, health
from src.api.webhooks import twilio, whatsapp

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info(f"Starting Sahayak {settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Sahayak")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="Sahayak",
    description=(
        "Zero-UI Agentic AI that lives on a phone line. "
        "Helping elderly users order medicines through voice interaction."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "An internal error occurred",
            "detail": str(exc) if settings.DEBUG else "Please try again later"
        }
    )


# Include routers
app.include_router(health.router)
app.include_router(voice.router)
app.include_router(wallet.router)
app.include_router(twilio.router)
app.include_router(whatsapp.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Sahayak",
        "version": settings.APP_VERSION,
        "description": "Zero-UI Agentic AI for Elderly Users",
        "status": "operational",
        "mvp_goal": "Can a non-technical senior successfully order medicine without calling their children for help?"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )