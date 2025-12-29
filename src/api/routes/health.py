"""
Health Check Routes
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime

from src.db.database import get_db
from src.config.settings import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check - verifies all dependencies
    """
    checks = {
        "database": False,
        "openai": False,
        "telephony": False
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database"] = str(e)
    
    # Check OpenAI (just verify key is set)
    checks["openai"] = bool(settings.OPENAI_API_KEY)
    
    # Check telephony (verify config is set)
    checks["telephony"] = bool(settings.TWILIO_ACCOUNT_SID) or settings.ENVIRONMENT == "development"
    
    all_healthy = all(v is True for v in checks.values())
    
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/live")
async def liveness_check():
    """Liveness check - is the service running"""
    return {"status": "alive"}