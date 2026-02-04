"""
FastAPI application entry point.
Responsibilities:
1.Initialize FastAPI app with metadata
2.Include routers from submodules
3.Configure CORS (development only)
4.Define root health check endpoint
5.Handle global exception hooks (future: logging, monitoring)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, submissions, admin, assets
from app.config import get_settings

settings = get_settings()

# ===============================
# APPLICATION INSTANCE
# ==============================

app = FastAPI(
    title="VERITAS Phase 1",
    description="Human-verified contribution system - API only",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc",  # ReDoc at /redoc
)

# =========================================
# CORS MIDDLEWARE (Development Only)
# =========================================

# Enable CORS for Postman/frontend testing
# WARNING: Remove in production or restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # CHANGE IN PRODUCTION
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================
# ROUTERS
# ============================

app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(submissions.router, prefix="/api", tags=["Submissions"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(assets.router, prefix="/api", tags=["Assets"])

# ===========================================================
# HEALTH CHECK
# ==========================================================
@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint.
    Returns:
        200 OK if service is running
    Use case
        - Load balancer health checks (future)
        - Quick connectivity test
        - Version verification
    """
    return {
        "status": "ok",
        "version": "0.1.0",
        "phase": "Phase 1 - Feasibility Probe"
    }

# ==================================================================
# STARTUP/SHUTDOWN EVENTS (Future: DB connection pooling, logging)
# ==================================================================

@app.on_event("startup")
async def startup_event():
    """
    Run once when server starts.
    Future use:
    - Verify database connection
    - Initialize connection pools
    - Load Configuration
    - Start background tasks
    """
    print("VERITAS Phase 1 starting...")
    print(f"    Database: {settings.DATABASE_URL}")
    print(f"    Token expiry: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Run once when server stops.
    Future use:
    - Close database connections
    - Flush logs
    - Cleanup temporary files
    """
    print("VERITAS Phase 1 shutting down...")


