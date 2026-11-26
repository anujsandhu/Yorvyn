"""FastAPI Application — Yorvyn Personal AI Stylist Platform"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
import logging
from .core.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Yorvyn – Personal AI Stylist API",
    description="Yorvyn Personal AI Fashion Intelligence, Digital Wardrobe, and Stylist Platform",
    version="3.0.0",
)


# Configure allowed origins based on debug mode
allowed_origins = ["*"] if settings.debug else [
    "https://yorvyn-ai.web.app",
    "https://yorvyn-ai.firebaseapp.com",
    "http://localhost:5174",
    "http://localhost:5173",
]

# Custom CORS & Observability middleware wrapper
class ObservabilityAndCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or f"req_{uuid.uuid4().hex[:12]}"
        )
        origin = request.headers.get("origin")
        
        # For development, allow all origins; for production, check whitelist
        if settings.debug:
            allowed = "*"
            send_credentials = "false"
        else:
            allowed = origin if origin in allowed_origins else None
            send_credentials = "true" if allowed else "false"
        
        # Handle CORS preflight requests
        if request.method == "OPTIONS":
            headers = {
                "Access-Control-Allow-Origin": allowed or origin or "*",
                "Access-Control-Allow-Credentials": send_credentials,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-Request-ID, X-Correlation-ID",
                "Access-Control-Expose-Headers": "X-Request-ID, X-Correlation-ID, X-Response-Time, *",
                "Access-Control-Max-Age": "86400",
                "X-Request-ID": correlation_id,
                "X-Correlation-ID": correlation_id,
            }
            return JSONResponse(content={"status": "ok"}, headers=headers)
        
        # Process actual request
        try:
            response = await call_next(request)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"[{correlation_id}] Request error on {request.method} {request.url.path} after {elapsed_ms:.2f}ms: {e}", exc_info=settings.debug)
            detail_msg = str(e) if settings.debug else "An internal server error occurred. Please try again later."
            response = JSONResponse(
                status_code=500,
                content={"detail": detail_msg, "type": type(e).__name__, "request_id": correlation_id, "correlation_id": correlation_id}
            )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
        
        # Add CORS headers to response
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Credentials"] = send_credentials
            response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Correlation-ID, X-Response-Time, *"
        elif not settings.debug:
            response.headers["Access-Control-Allow-Origin"] = origin or allowed_origins[0]
            response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Correlation-ID, X-Response-Time, *"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Correlation-ID, X-Response-Time, *"
        
        logger.info(f"[{correlation_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.2f}ms)")
        return response

# Add custom observability & CORS middleware FIRST
app.add_middleware(ObservabilityAndCORSMiddleware)

# Standard CORS middleware (provides automatic OPTIONS handling via starlette)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=not settings.debug,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# Startup event
@app.on_event("startup")
async def startup_event():
    settings.log_status()
    try:
        from backend.app.services.garments.job_manager import garment_job_manager
        recovered = garment_job_manager.recover_stranded_jobs()
        if recovered > 0:
            logger.info(f"🧹 Recovered {recovered} stranded jobs on startup.")
        garment_job_manager.start_outbox_dispatcher()
    except Exception as e:
        logger.warning(f"Startup job recovery notice: {e}")
    logger.info("🚀 Yorvyn Fashion Intelligence Core ready")


@app.on_event("shutdown")
async def shutdown_event():
    try:
        from backend.app.services.garments.job_manager import garment_job_manager
        garment_job_manager.stop_outbox_dispatcher()
    except Exception:
        pass

# Mount Fashion Intelligence routes
from backend.app.api.fashion_routes import router as fashion_router
from backend.app.api.garment_generation_routes import router as garment_3d_router
from backend.app.api.speech_routes import router as speech_router
from backend.app.api.billing_routes import router as billing_router
from backend.app.api.beta_routes import router as beta_router
from backend.app.api.ops_routes import router as ops_router
from backend.app.api.ai_session_routes import router as ai_session_router
from backend.app.api.learning_routes import router as learning_router
from backend.app.api.ai_orchestration_routes import router as ai_orchestration_router
from backend.app.api.garment_identification_routes import router as garment_identification_router
from backend.app.api.intelligence_routes import router as intelligence_router

app.include_router(fashion_router)
app.include_router(garment_3d_router)
app.include_router(garment_identification_router)
app.include_router(speech_router)
app.include_router(billing_router)
app.include_router(beta_router)
app.include_router(ops_router)
app.include_router(ai_session_router)
from backend.app.api.conversational_garments import router as conversational_garments_router
from backend.app.api.garment_design_routes import router as garment_design_router
from backend.app.api.motion_routes import router as motion_router
app.include_router(conversational_garments_router)
app.include_router(garment_design_router)
app.include_router(motion_router)
app.include_router(learning_router)
app.include_router(intelligence_router)
app.include_router(ai_orchestration_router)
app.include_router(ai_orchestration_router, prefix="/api/fashion")



@app.get("/")
def root():
    return {
        "message": "Yorvyn API",
        "docs": "/docs",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
async def favicon():
    from fastapi import Response
    return Response(status_code=204)


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ready",
        "service": "Yorvyn Fashion Intelligence Core",
        "version": "3.0.0",
        "environment": settings.environment,
        "database": "supabase" if (settings.supabase_url and "supabase" in settings.supabase_url) else "sqlite_local",
        "storage": "cloudinary" if settings.cloudinary_cloud_name else "local_disk",
        "ai_providers": {
            "groq": settings.has_groq,
            "gemini": settings.has_gemini,
            "openrouter": settings.has_openrouter,
            "openai": settings.has_openai,
            "hf": settings.has_hf
        },
        "fashion_domains": ["profile", "wardrobe", "outfits", "stylist", "avatar", "cloth_physics", "3d_reconstruction"],
    }


@app.get("/metrics")
@app.get("/api/metrics")
def get_system_metrics():
    """Provides operational metrics, hardware RSS, and AI job queue telemetry."""
    import sys
    import resource
    from backend.app.services.garments.job_manager import garment_job_manager
    rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 / 1024.0, 2)
    job_health = garment_job_manager.get_health_status()

    return {
        "status": "healthy",
        "service": "Yorvyn Platform Metrics",
        "system": {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "peak_rss_mb": rss_mb
        },
        "worker_telemetry": job_health,
        "database_connected": bool(settings.supabase_url and not settings.supabase_url.startswith("https://demo")),
        "timestamp": time.time()
    }



# Global error handler — ensure CORS headers preserved
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    logger.error(f"Unhandled error: {error_msg}", exc_info=exc)
    
    # Return error with CORS headers (middleware will also add them)
    response = JSONResponse(
        status_code=500, 
        content={
            "detail": error_msg,
            "type": type(exc).__name__,
            "path": str(request.url),
        }
    )
    
    # Explicitly set CORS headers on error response
    origin = request.headers.get("origin", "*")
    allowed_origins_list = ["*"] if settings.debug else [
        "https://yorvyn-ai.web.app",
        "https://yorvyn-ai.firebaseapp.com",
        "http://localhost:5174",
        "http://localhost:5173",
    ]
    
    response.headers["Access-Control-Allow-Origin"] = "*" if settings.debug else origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
