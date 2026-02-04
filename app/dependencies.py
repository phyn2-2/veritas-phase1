"""
FastAPI dependency injection for database sessions, authentication and authorization.
Design principles:
1. Dependencies are stateless (no side effects)
2. Each dependency has a single responsibility
3. Auth failures raise HTTPException (FastAPI handles response)
4. Database sessions auto-close via context manager
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Annotated
from app.database import get_db
from app.models import User
from app.auth import decode_access_token

# =======================================
# DATABASE DEPENDENCY
# =======================================

# Type alias for cleaner endpoint signatures
DbSession = Annotated[Session, Depends(get_db)]

# ===============================
# AUTHENTICATION DEPENDENCIES
# ==============================

# HTTP Bearer token scheme (Authorization: Bearer <token>)
security = HTTPBearer(
    scheme_name="Bearer",
    description="JWT access token",
    auto_error=True  # Automatically return 401 if missing
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate JWT, return authenticated user.

    Flow:
    1.Extract token from Authorization header (HTTPBearer handles)
    2.Decode JWT and validate signature/expiration
    3.Query user from database by token's 'sub' claim
    4.Return user object or raise 401

    Failure modes:
    - Missing token -> HTTPBearer raises 401 automatically
    - Invalid/expired token -> decode_access_token returns None -> 401
    - User not found (deleted after token issued) -> 401
    - Token valid but user.is_admin changed -> Fresh data from DB

    Security:
    - Token decode happens first (cheap check before db query)
    - No timing attacks (constant-time JWT validation)
    - User state refreshed from DB (not cached from token)

    Wht async: Future-proofs for async DB drivers (SQLAlchemy 2.0+)
    Current: No performance benefit (SQLite is sync), but FastAPI compatible
    """
    token = credentials.credentials

    # Decode and validate JWT
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Query user from database
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        # User deleted after token issued (rare but possible)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

# Type alias for authenticated endpoints
CurrentUser = Annotated[User, Depends(get_current_user)]

# ===================================
# AUTHORIZATION DEPENDENCIES
# ==================================
async def require_admin(current_user: CurrentUser) -> User:
    """
    Enforce admin-only access.
    Flow:
    1.Requires get_current_user (dependency chain)
    2.Check is_admin flag from database (not token claim)
    3.Return user if admin, else 403

    Why separate from get_current_user:
    - Single Responsibility Principle (auth vs. authz)
    - Allows non-admin endpoints to use get_current_user
    - Per-endpoint admin check (explicit in router signatures)

    Why query DB for is_admin:
    - Token may be stale (admin demoted after token issued)
    - Source of truth is database, not JWT claim

    Trade-off:
    - Pro: Always current permissions
    - Gotcha: Extra DB query (acceptable for Phase 1 admin-only ops)

    Failure mode:
    - Non-admin tries admin endpoint -> 403 FORBIDDEN
    - Token has is_admin=true but DB has false -> 403 (DB wins)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Type alias for admin-only endpoints
AdminUser = Annotated[User, Depends(require_admin)]


# ============================================================
# HELPER FUNCTIONS (Not dependencies, but used in endpoints)
# ===============================================================
def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    """
    Find user by email OR username.
    Used in login endpoint to support flexible authentication.

    Why separate function:
    - Reusable logic (could be used in password, reset, etc.)
    - Keeps endpoint code clean
    - Single query (OR filter, not two queries)

    Perfomance:
    - Indexed columns (email, username) make this efficient
    - Single DB round-trip

    Returns None if not found (caller handles 401).
    """
    return db.query(User).filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()


