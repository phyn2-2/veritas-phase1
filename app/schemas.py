"""
Pydantic schemas for request/response validation.
Separation of concerns:
- Models (ORM): Database persistence, relationships
- Schemas: API transport, validation, sanitization

Never expose password_hash or internal IDs in responses.
"""
from pydantic import BaseModel, EmailStr, HttpUrl, field_validator, ConfigDict
from typing import Optional, Literal, Generic, TypeVar, List
from datetime import datetime
from app.models import ContributionType, ContributionStatus, VerificationDecision

T = TypeVar("T")

# =========================
# USER SCHEMAS
# ========================

class UserBase(BaseModel):
    """Shared user fields"""
    email: EmailStr  # Validates email format
    username: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Username constraints:
        - 3-50 chars
        - Alphanumeric + underscore only
        - No whitespace

        Why: Prevents SQL injection attempts, ensures URL-safe usernames
        """
        if not v:
            raise ValueError("Username required")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be 3-50 characters")
        if not v.replace('_', '').isalnum():
            raise ValueError("Username must be alphanumeric (underscores allowed)")
        return v.lower()  # Normalize to lowercase

class UserCreate(UserBase):
    """Reqistration request"""
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Password strength requirements:
        - Min 8 chars
        - At least one uppercase, lowercase, digit

        Why: Balances security with UX (no special char requirement for Phase 1)
        Trade-off: Weak passwords allowed; Phase 2 adds entropy checks.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v

class UserLogin(BaseModel):
    """Login request"""
    identifier: str  # Email OR username
    password: str

class UserResponse(UserBase):
    """Public user data (no password_hash)"""
    id: int
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    token_type: str = "bearer"


# ================================
# CONTRIBUTION SCHEMAS
# ===============================

class ContributionBase(BaseModel):
    """Shared contribution fields"""
    title: str
    description: str
    type: ContributionType
    file_url: Optional[HttpUrl] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """
        Title constraints:
        - Required, non-empty after strip
        - Max 200 chars (matches DB column)
        - No leading/trailing whitespace
        """
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 200:
            raise ValueError("Title max 200 characters")
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """
        Description constraints:
        - Required, non-empty
        - Max 10,000 chars(well below SQLite TEXT limit, reasonable for Phase 1)

        Why 10k cap: Prevents abuse (massive submissions), ensures reasonable review time.
        """
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty")
        if len(v) > 10000:
            raise ValueError("Description max 10,000 characters")
        return v

    @field_validator('file_url')
    @classmethod
    def validate_file_url(cls, v: Optional[HttpUrl]) -> Optional[str]:
        """
        File URL constraints:
        - HTTPS only (Failure Mode #5: security)
        - Max 500 chars (matches DB column)

        Why HTTPS: Prevents MITM attacks, enforces modern standards.
        Trade-off: Excludes HTTP-only legacy hosts (acceptable for Phase 1).
        """
        if v is None:
            return None

        url_str = str(v)
        if not url_str.startswith("https://"):
            raise ValueError("Only HTTPS URLs allowed")
        if len(url_str) > 500:
            raise ValueError("URL max 500 characters")
        return url_str

class ContributionCreate(ContributionBase):
    """Submission creation request"""
    pass  # Inherits all validation from ContributionBase

class ContributionResponse(ContributionBase):
    """Contribution with metadata"""
    id: int
    user_id: int
    status: ContributionStatus
    created_at: datetime
    updated_at: datetime

    # Optional: Include user info (avoids N+1 in listings)
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)

# =============================
# VERIFICATION SCHEMAS
# ============================

class VerificationRequest(BaseModel):
    """Admin verification decision"""
    decision: VerificationDecision
    notes: Optional[str] = None

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """
        Notes constraints:
        - Optional
        - Max 5,000 chars provided
        - Stripped of leading/trailing whitespace
        """
        if v is None:
            return None
        v = v.strip()
        if len(v) > 5000:
            raise ValueError("Notes max 5,000 characters")
        return v if v else None  # Convert empty string to None

class VerificationResponse(BaseModel):
    """Verification log entry (audit trail)"""
    id: int
    contribution_id: int
    admin_id: int
    decision: VerificationDecision
    notes: Optional[str]
    timestamp: datetime

    # Optional: Include admin info
    admin: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


# =======================
# PAGINATION SCHEMAS
# =======================
class PaginationParams(BaseModel):
    """Reusable pagination parameters"""
    page: int = 1
    limit: int = 50

    @field_validator('page')
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Page must be >= 1")
        return v

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """
        Limit constraints:
        - Min 1, max 100 (prevents oversized responses)

        Why max 100: Balances UX (fewer round-trips) with server load.
        """
        if v < 1:
            raise ValueError("Limit must be >= 1")
        if v > 100:
            raise ValueError("Limit max 100")
        return v

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper"""
    data: List[T]
    pagination: dict

    @classmethod
    def create(cls, data: list, page: int, limit: int, total: int):
        """
        Factory method for consistent pagination metadata.
        """
        return cls(
            data=data,
            pagination={
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        )




