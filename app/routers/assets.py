"""
Assets router: Public verified contributions and file management
Business rules:
1. GET /assets returns only VERIFIED contributions (public)
2. No authentication required for viewing (public discovery)
3. File presigning is placeholder in Phase 1 (no real storage)
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload
from app.dependencies import DbSession, CurrentUser
from app.schemas import ContributionResponse, PaginationParams
from app.models import Contribution, ContributionStatus
from pydantic import BaseModel

router = APIRouter()

@router.get(
    "/assets",
    response_model=list[ContributionResponse],
    summary="Get all verified assets",
    responses={
        200: {"description": "List of verified contributions (public)"}
    }
)
async def get_verified_assets(
    db: DbSession,
    pagination: PaginationParams = PaginationParams()
):
    """
    Retrieve all VERIFIED contributions (public asset pool).
    Public endpoint:
    - No authentication required
    - Only VERIFIED status visible (PENDING/REJECTED hidden)
    - Intended for public discovery/browsing

    Query optimization:
    - Filtered by VERIFIED status (indexed)
    - Ordered by creation time (newest first)
    - Eager-loads user for attribution

    Future enhancements (Phase 2):
    - Filter by type (idea/work/asset)
    - Search by keywords
    - Sort options (popular, recent, alphabetical)

    Scale consideration:
    - At 10k assets, add composite index on (status, created_at)
    - Consider caching for homepage featured assets
    """
    offset = (pagination.page - 1) * pagination.limit

    assets = db.query(Contribution).options(
        joinedload(Contribution.user)
    ).filter(
        Contribution.status == ContributionStatus.VERIFIED
    ).order_by(
        Contribution.created_at.desc()  # Newest first
    ).offset(offset).limit(pagination.limit).all()

    return assets

# ===================================================================
# FILE PRESIGNING (Phase 1: Placeholder only)
# ===================================================================

class PresignRequest(BaseModel):
    """File metadata for presigned URL generation"""
    filename: str
    content_type: str

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "document.pdf",
                "content_type": "application/pdf"
            }
        }

class PresignResponse(BaseModel):
    """Presigned URL response (placeholder)"""
    upload_url: str
    file_url: str
    expires_in: int

    class Config:
        json_schema_extra = {
            "example": {
                "upload_url": "https://placeholder.example.com/upload",
                "file_url": "https://placeholder.example.com/files/abc123",
                "expires_in": 3600
            }
        }

@router.post(
    "/assets/presign",
    response_model=PresignResponse,
    summary="Generate presigned upload URL (placeholder)",
    responses={
        200: {"description": "Presigned URL generated"},
        401: {"description": "Not authenticated"}
    }
)
async def generate_presigned_url(
    request: PresignRequest,
    current_user: CurrentUser,
    db: DbSession
):
    """
    Generate presigned URL for file upload.
    Phase 1 behavior:
    - Returns placeholder URLs (no actual storage backend)
    - Validates file metadata only
    - Authenticates user but doesn't track uploads

    Phase 2 implementation would:
    - Integrate with S3/GCS/Azure Blob Storage
    - Generate real presigned URLs (PUT /upload, GET /download)
    - Track upload completion
    - Validate file size/type server-side
    - Associate uploaded file with contribution

    Current Validation:
    - Filename required (non-empty)
    - Content-type required (MIME Validation)
    - User must be authenticated

    Why placeholder:
    - Phase 1 excludes file storage (external URLs only)
    - Demonstrates API contract for future implementation
    - Prevents scope creep while showing desugn intent
    """
    # Validate filename
    if not request.filename or not request.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename required"
        )

    # Validate content type
    allowed_types = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "application/zip",
        "text/plain"
    ]

    if request.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Content type not allowed. Allowed: {', '.join(allowed_types)}"
        )

    # Return placeholder response
    # Phase 2: Replace with actual S3/GCS presigned URL generation
    return PresignResponse(
        upload_url="https://placeholder.example.com/upload/abc123",
        file_url="https://placeholder.example.com/files/abc123",
        expires_in=3600  # 1 hour
    )




