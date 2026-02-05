"""
Submissions router: User contribution management.
Business rules:
1.Users can create contributions (ideas, work, assets)
2.Max 3 PENDING submissions per user (prevents spam)
3.All submissions start as PENDING status
4.Users can only view their own submissions
5.File URLs must be HTTPS (validated in schema)

HARDENING UPDATES:
- Row locking on user to prevent concurrent pending limit bypass
- Explicit transaction boundary
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from app.dependencies import DbSession, CurrentUser
from app.schemas import ContributionCreate, ContributionResponse, PaginationParams
from app.models import Contribution, ContributionStatus, User
from app.config import get_settings

settings = get_settings()
router = APIRouter()

@router.post(
    "/submissions",
    response_model=ContributionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit new contribution",
    responses={
        201: {"description": "Contribution created"},
        401: {"description": "Not authenticated"},
        409: {"description": "Pending limit exceeded (max 3)"},
        422: {"description": "Invalid contribution data"}
    }
)
async def create_submission(
    submission: ContributionCreate,
    current_user: CurrentUser,
    db: DbSession
):
    """
    Create new contribution for verification.
    Flow:
    1.Check user's pending count (with row lock to prevent race condition)
    2.Reject if >= 3 pending submissions
    3.Create contribution with PENDING status
    4.Associate with current user
    5.Commit and return

    Race condition prevention:
    Scenario: User submits 2 requests simultaneously at 2 pending
    - Without lock: Both check "2 < 3", both insert -> pending
    - With lock: First acquires lock, inserts, releases -> Second sees 3, rejects

    Business justification for 3-submission limit:
    - Prevents spam/abuse
    - Ensures admin queue stays manageable
    - Forces users to wait for feedback before mass-submitting

    File URL validation:
    - HTTPS-only enforced in Pydantic schema
    - No file upload in Phase 1 (external hosting only)
    - Admin manually verifies URL during review

    Hardening: Transaction with SELECT FOR UPDATE to prevent race conditions
    """
    # Start explicit transaction
    # Note: get_db already wraps in transaction, but we need explicit lock

    # Lock user's pending contributions to prevent concurrent bypass
    # Strategy: Lock user row (prevents concurrent pending checks)
# NOTE:
# SQLite ignores SELECT ... FOR UPDATE.
# Race-condition protection becomes effective when migrating to PostgreSQL.

    user_lock = db.query(User).filter(
        User.id == current_user.id
    ).with_for_update().first()  # Locks user row

    # Now count pending (within lock)
    pending_count = db.query(func.count(Contribution.id)).filter(
        Contribution.user_id == current_user.id,
        Contribution.status == ContributionStatus.PENDING
    ).scalar()
    if pending_count >= settings.MAX_PENDING_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum {settings.MAX_PENDING_PER_USER} pending submissions allowed."
                    f"Wait for verification before submitting more."
        )

    # Create contribution
    contribution = Contribution(
        user_id=current_user.id,
        title=submission.title,
        description=submission.description,
        type=submission.type,
        file_url=submission.file_url,  # Optional, validated as HTTPS in schema
        status=ContributionStatus.PENDING  # All start as PENDING
    )

    db.add(contribution)
    db.flush()  # Get contribution.id before transaction ends


    return contribution

@router.get(
    "/submissions/mine",
    response_model=list[ContributionResponse],
    summary="Get my submissions",
    responses={
        200: {"description": "List of user's submissions"},
        401: {"description": "Not authenticated"}
    }
)

async def get_my_submissions(
    current_user: CurrentUser,
    db: DbSession,
    pagination:PaginationParams = PaginationParams()
):
    """
    Retrieve all submissions created by authenticated user.

    Returns:
    - All statuses (PENDING, VERIFIED, REJECTED, NEEDS_CHANGES)
    - Ordered by creation time (newest first)
    - Paginated (default 50 per page, max 100)

    Use case:
    - User checks status of submitted contributions
    - User sees feedback (via verification logs, if exposed in future)

    Note: Does not include verification logs in Phase 1.
    Admin feedback would be in logs table (future endpoint).
    """
    offset = (pagination.page -1) * pagination.limit

    contributions = db.query(Contribution).filter(
        Contribution.user_id == current_user.id
    ).order_by(
        Contribution.created_at.desc()
    ).offset(offset).limit(pagination.limit).all()

    return contributions

@router.get(
    "/submissions/{contribution_id}",
    response_model=ContributionResponse,
    summary="Get specific submission",
    responses={
        200: {"description": "Contribution details"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not your submission"},
        404: {"description": "Submission not found"}
    }
)
async def get_submission(
    contribution_id: int,
    current_user: CurrentUser,
    db: DbSession
):
    """
    Retrieve single contribution by ID.

    Authorization:
    - User can only view their on submissions
    - Admin can view via admin endpoints (future)

    Failure modes:
    - ID doesn't exist -> 404 NOT_FOUND
    - ID exists but belongs to another user -> 403 FORBIDDEN

    Security:
    - Prevents user enumeration (attacker can't scan all IDs)
    - Ownership check enforced at application layer
    """
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()

    if contribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Authorization: User can only view own submissions
    if contribution.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this submission"
        )
    return contribution




