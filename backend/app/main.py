"""FastAPI Application — Yorvyn Personal AI Stylist Platform"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from .core.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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

# Custom CORS middleware wrapper — ensures CORS headers on ALL responses
class CORSHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
                "Access-Control-Expose-Headers": "*",
                "Access-Control-Max-Age": "86400",
            }
            return JSONResponse(content={"status": "ok"}, headers=headers)
        
        # Process actual request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request error: {e}", exc_info=True)
            response = JSONResponse(
                status_code=500,
                content={"detail": str(e), "type": type(e).__name__}
            )
        
        # Add CORS headers to response
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Credentials"] = send_credentials
            response.headers["Access-Control-Expose-Headers"] = "*"
        elif not settings.debug:
            # For non-debug mode, still send CORS headers to avoid blocking
            response.headers["Access-Control-Allow-Origin"] = origin or allowed_origins[0]
            response.headers["Access-Control-Expose-Headers"] = "*"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Expose-Headers"] = "*"
        
        return response

# Add custom CORS middleware FIRST (before other middleware)
app.add_middleware(CORSHeaderMiddleware)

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
    logger.info("🚀 Yorvyn Fashion Intelligence Core ready")

# Mount Fashion Intelligence routes
from backend.app.api.fashion_routes import router as fashion_router
from backend.app.api.garment_generation_routes import router as garment_3d_router
app.include_router(fashion_router)
app.include_router(garment_3d_router)



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
        "fashion_domains": ["profile", "wardrobe", "outfits", "stylist", "avatar"],
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
