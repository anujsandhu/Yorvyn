"""FastAPI Application — Yorvyn (No Auth)"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import threading
from .config import settings
from .api import recommendation_routes
from .api import ai_routes
from .api import chat_routes
from .api import chat_routes_ai_upgrade
from .api import recommend_routes
from .ai_fallback import get_ai_status
from .ai_recommendation_engine import initialize_ai_engine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Yorvyn perfume recommendation system",
    version="2.0.0",
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


def _load_models_background():
    """
    Load ML models in a background thread so the server starts instantly.
    Routes return 503 until this completes (~25s on cold start).
    """
    import time
    from .ml_model import recommender
    from .ai_recommendation_engine import initialize_ai_engine
    
    # Use direct stderr writes to ensure visibility even if logging fails
    print("🔄 Loading ML models in background thread...", file=__import__('sys').stderr, flush=True)
    logger.info("🔄 Loading ML models in background thread...")
    start = time.time()
    try:
        print(f"   Checking models_dir: {recommender.models_dir}", file=__import__('sys').stderr, flush=True)
        print(f"   Checking data_dir: {recommender.data_dir}", file=__import__('sys').stderr, flush=True)
        
        if recommender._load_pretrained_models():
            print("   ✓ Pre-trained models loaded successfully", file=__import__('sys').stderr, flush=True)
            recommender._prepare_runtime_artifacts()
            recommender.__class__._models_trained = True
            elapsed = time.time() - start
            perfume_count = len(recommender.data) if recommender.data is not None else 0
            msg = f"✅ ML models ready in {elapsed:.1f}s — {perfume_count:,} perfumes loaded"
            print(msg, file=__import__('sys').stderr, flush=True)
            logger.info(msg)
            
            # NOW initialize AI engine after data is loaded
            try:
                initialize_ai_engine()
                print("   ✓ AI recommendation engine initialized", file=__import__('sys').stderr, flush=True)
                logger.info("✅ AI recommendation engine initialized with dataset")
            except Exception as e:
                print(f"   ⚠️  AI engine initialization failed: {e}", file=__import__('sys').stderr, flush=True)
                logger.warning(f"⚠️  AI engine initialization failed: {e}")
        else:
            print("   ⚠️  Pre-trained models not found, attempting training from scratch...", file=__import__('sys').stderr, flush=True)
            logger.warning("⚠️  Pre-trained models not found, training from scratch...")
            recommender._load_all_datasets()
            if recommender.data is not None and len(recommender.data) > 0:
                print(f"   Loaded {len(recommender.data)} perfumes, training models...", file=__import__('sys').stderr, flush=True)
                recommender._train_all_models()
                elapsed = time.time() - start
                msg = f"✅ Training complete in {elapsed:.1f}s"
                print(msg, file=__import__('sys').stderr, flush=True)
                logger.info(msg)
                
                # Initialize AI engine after training
                try:
                    from .ai_recommendation_engine import initialize_ai_engine
                    initialize_ai_engine()
                    print("   ✓ AI recommendation engine initialized", file=__import__('sys').stderr, flush=True)
                    logger.info("✅ AI recommendation engine initialized with dataset")
                except Exception as e:
                    print(f"   ⚠️  AI engine initialization failed: {e}", file=__import__('sys').stderr, flush=True)
                    logger.warning(f"⚠️  AI engine initialization failed: {e}")
            else:
                print("   ❌ No data available — check data/ directory", file=__import__('sys').stderr, flush=True)
                logger.error("❌ No data available — check data/ directory")
    except Exception as e:
        import traceback
        error_msg = f"❌ Background model loading failed: {e}"
        print(error_msg, file=__import__('sys').stderr, flush=True)
        print(traceback.format_exc(), file=__import__('sys').stderr, flush=True)
        logger.error(error_msg, exc_info=True)


# Startup event — server accepts connections immediately, models load in background
@app.on_event("startup")
async def startup_event():
    settings.log_status()
    t = threading.Thread(target=_load_models_background, daemon=True, name="ml-loader")
    t.start()
    logger.info("🚀 Server ready — ML models loading in background")
    
    # Initialize AI recommendation engine (after models are loaded)
    try:
        initialize_ai_engine()
        logger.info("✅ AI recommendation engine initialized")
    except Exception as e:
        logger.warning(f"⚠️  AI recommendation engine initialization deferred: {e}")

# Include routes (no auth)
app.include_router(
    recommendation_routes.router,
    prefix="/api",
    tags=["recommendations", "perfumes", "stats"],
)
app.include_router(
    ai_routes.router,
    prefix="/api",
    tags=["ai", "shopping"],
)
app.include_router(
    chat_routes.router,
    prefix="/api",
    tags=["chat"],
)
app.include_router(
    chat_routes_ai_upgrade.router,
    prefix="/api",
    tags=["ai-chat-v2"],
)
app.include_router(
    recommend_routes.router,
    prefix="/api",
    tags=["recommend"],
)
from .fashion import fashion_router
app.include_router(fashion_router)


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
    from .ml_model import recommender

    try:
        info = recommender.get_model_info()
        is_ready = (recommender.data is not None and
                   len(recommender.data) > 0 and
                   recommender.tfidf_vectorizer is not None)

        return {
            "status": "ready" if is_ready else "loading",
            "dataset_size": info["dataset_size"],
            "models_trained": info["models_trained"],
            "tfidf_ready": recommender.tfidf_vectorizer is not None,
            "data_loaded": recommender.data is not None and len(recommender.data) > 0,
            "ai_providers": get_ai_status(),
        }
    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "dataset_size": 0,
            "models_trained": False,
            "ai_providers": get_ai_status(),
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
