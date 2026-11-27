"""FastAPI Application — Yorvyn Personal AI Stylist Platform"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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


from collections import defaultdict, deque
import threading

# Configure explicit CORS allowlist (never reflect arbitrary Origin, never combine '*' with credentials)
allowed_origins = list(settings.cors_allowed_origins)

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_RULES = (
    ("/api/fashion/garment-gen/jobs", 30, 60),
    ("/api/garments/identify", 30, 60),
    ("/api/garments/hybrid-orchestrated-identify", 30, 60),
    ("/api/intelligence/", 60, 60),
    ("/api/fashion/speech/", 30, 60),
)


class ObservabilitySecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or f"req_{uuid.uuid4().hex[:12]}"
        )

        # Lightweight sliding-window rate limit for upload/generation/LLM paths
        path = request.url.path
        for prefix, max_reqs, window_sec in _RATE_LIMIT_RULES:
            if path.startswith(prefix) and request.method in ("POST", "PUT", "PATCH"):
                client_ip = request.client.host if request.client else "unknown"
                bucket_key = f"{client_ip}:{prefix}"
                now = time.time()
                with _RATE_LIMIT_LOCK:
                    q = _RATE_LIMIT_BUCKETS[bucket_key]
                    while q and now - q[0] > window_sec:
                        q.popleft()
                    if len(q) >= max_reqs:
                        return JSONResponse(
                            status_code=429,
                            content={"error": "rate_limit_exceeded", "request_id": correlation_id},
                            headers={"Retry-After": str(window_sec), "X-Request-ID": correlation_id},
                        )
                    q.append(now)
                break

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"[{correlation_id}] Unhandled error on {request.method} {request.url.path} after {elapsed_ms:.2f}ms: {e}",
                exc_info=True,
            )
            if settings.debug:
                body = {"error": "internal_error", "detail": str(e), "type": type(e).__name__, "request_id": correlation_id}
            else:
                body = {"error": "internal_error", "request_id": correlation_id}
            response = JSONResponse(status_code=500, content=body)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"

        logger.info(f"[{correlation_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.2f}ms)")
        return response


app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(ObservabilitySecurityAndRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID", "X-Correlation-ID", "X-Idempotency-Key", "X-Admin-Key"],
    expose_headers=["X-Request-ID", "X-Correlation-ID", "X-Response-Time"],
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



# Global error handler — never leak internal stack/exception details in non-debug mode
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    logger.error(f"[{request_id}] Unhandled error: {error_msg}", exc_info=exc)

    if settings.debug:
        content = {
            "error": "internal_error",
            "detail": error_msg,
            "type": type(exc).__name__,
            "request_id": request_id,
        }
    else:
        content = {
            "error": "internal_error",
            "request_id": request_id,
        }

    return JSONResponse(status_code=500, content=content)


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "127.0.0.1"),
        port=8001,
        log_level="info",
    )
