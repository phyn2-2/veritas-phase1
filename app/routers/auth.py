"""
Authentication router: Registration and login endpoints.
Business rules:
1.Registration creates non-admin users by default (least privilege)
2.Email and username must be unique (enforced by DB constraints; conflicts handled at API layer)
3.Passwords are hashed before storage (never plaintext)
4.Login accepts Email OR username as identifier
5.JWT tokens include user_id (sub), admin status, and expiration
6.Timing attack mitigation: Hash dummy password for non-existent users
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from app.dependencies import DbSession, get_user_by_identifier
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.models import User
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Invalid input data"},
        409: {"description": "Email or username already exists"}
    }
)
async def register(user_data: UserCreate, db: DbSession):
    """
    Create new user account.
    Flow:
    1.Validate input via Pydantic (UserCreate schema)
    2.Hash password using bcrypt
    3.Create user with is_admin=False (default)
    4.Commit to database
    5.Return user data (no password_hash)

    Failure modes:
    - Duplicate email -> IntegrityError -> 409 CONFLICT
    - Duplicate username -> IntegrityError -> 409 CONFLICT
    - Weak password -> Pydantic validation -> 400 BAD_REQUEST
    - Invalid email format -> Pydantic validation -> 400 BAD_REQUEST

    Security:
    - Password Validated in schema (8+ chars, mixed case, digit)
    - Password hashed with bcrypt (cost factor 12)
    - Admin status defaults to False (explicit escalation required)
    - Username normalized to lowercase (prevents "Admin" vs "admin")

    Note: First admin must be created via bootstrap script.
    """
    # Create user instance (password hashed here before storage)
    user = User(
        email=user_data.email,
        username=user_data.username,  # Already lowercased by schema validator
        password_hash=hash_password(user_data.password),
        is_admin=False  # Explicit: Never allow self-registration as admin
    )

    try:
        db.add(user)
        db.flush()

        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_admin": user.is_admin
        }


    except IntegrityError as e:
        db.rollback()
        # Parse error to determine which constraint failed
        error_msg = str(e.orig)
        if "email" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        elif "username" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )
        else:
            # Generic constraint violation
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists"
            )

    return user

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and receive JWT",
    responses={
        200: {"description":"Login successful, token returned"},
        401: {"description": "Invalid credentials"}
    }
)
async def login(credentials: UserLogin, db: DbSession):
    """
    Authenticate user with email/username and password.
    Flow:
    1.Query user by identifier (email OR username)
    2.Verify password against stored hash
    3.Generate JWT with user claims
    4.Return token

    Failure modes:
    - User not found -> Hash dummy password -> 401 (timing attack mitigation)
    - Wrong password -> 401
    - Account exists but validation fails -> 401

    Security - Timing Attack Mitigation (Failure Mode #4):
    Problem: Attacker measures response time to determine valid usernames.
    - Valid user + wrong password: ~300ms (bcrypt verification)
    - Invalid user: ~5ms (no hash verification)

    Solution: Always hash dummy password for non-existent users.
    - Valid user: Query DB + bcrypt verify = ~300ms
    - Invalid user: Query DB + dummy bcrypt = ~300ms

    This equalizes timing, preventing username enumeration.

    JWT claims:
    - sub: User ID (string representation)
    - is_admin: Boolean (admin role)
    - exp: Expiration timestamp (UTC)
    """
    # Query user by email OR username
    user = get_user_by_identifier(db, credentials.identifier)

    if user is None:
        # Timing attack mitigation: Hash dummy password to match valid user timing
        # This prevents Attackers from detecting valid usernames via response time
        hash_password("dummy_password_to_equalize_timing_12345")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    # Generate JWT
    access_token = create_access_token(
        data={
            "sub": str(user.id),  # Subject: user identifier
            "is_admin": user.is_admin  # Role claim (but always check DB in dependencies)
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )




