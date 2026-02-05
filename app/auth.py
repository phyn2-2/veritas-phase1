from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
import jwt
from app.config import get_settings

def get_auth_settings():
    return get_settings()

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Cost factor: 2^12 iterations (~300ms)
    bcrypt__ident="2b"
)

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    Why bcrypt: Intentionally slow (defeats brute-force), salted automatically.
    Cost factor 12 = ~300ms on modern CPU (acceptable UX delay).
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.

    Timing attack mitigation: bcrypt.verify() is constant-time for valid hashes.
    Caller must hash dummy password for non-existent users (Failure Mode #4).
    """
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.verify(password_bytes, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate JWT with user claims.
    Token structure:
    {
    "sub": "user_id",               # Subject (user identifier)
    "is_admin": true/false          # Role claim
    "exp": 1234567890               # Expiration (UTC timestamp)
    }
    Security: Short TTL (30min) limits blast radius if leaked.
    No refresh tokens in Phase 1 (user re-authenticates).
    """
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    print("ENCODE SECRET:", settings.SECRET_KEY)
    print("ENCODE ALG:", settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """
    Validate and decode JWT.
    Returns payload if valid, None otherwise.
    Failure modes:
    - Expired token -> jwt.ExpiredSignatureError
    - Invalid signature -> jwt.InvalidTokenError
    - Malformed token -> jwt.DecodeError

    All exceptions caught and return None (fail-safe).
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        print("DECODE SECRET:", settings.SECRET_KEY)
        print("DECODE ALG:", settings.ALGORITHM)
        return payload
    except jwt.ExpiredSignatureError:
        # Token expired (normal after 30min)
        return None
    except jwt.InvalidTokenError:
        # Tampered/malformed token
        return None



