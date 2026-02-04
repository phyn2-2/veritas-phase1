"""
Admin router: Verification and moderation endpoints.

Business rules:
1. Only admins can assess these endpoints
2. Verification is idempotent (safe to call multiple times)
3. Every Verification decision is logged immutably
4. Transactional updates (status + log must succeed together)
5. Row locking prevents concurrent Verification race conditions
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload
from app.dependencies import DbSession, AdminUser
from app.schemas import (
    VerificationRequest,
    ContributionResponse,
    PaginationParams
)
from app.models import (
    Contribution,
    ContributionStatus,
    VerificationLog,
    VerificationDecision
)

router = APIRouter()

@router.get(
    "/pending",
    response_model=list[ContributionResponse],
    summary="Get all pending submissions",
    responses={
        200: {"description": "List of pending contributions"},
        401: {"description": "Not authenticated"},
        403: {"description": "Admin access required"}
    }
)
async def get_pending_submissions(
    admin: AdminUser,
    db: DbSession,
    pagination: PaginationParams = PaginationParams()
):
    """
    Retrieve all contributions awaiting verification.

    Query optimization:
    - Filtered by PENDING status (indexed column)
    - Ordered by creation time (FIFO fairness)
    - Paginated to prevent large result sets
    - Eager-loads user relationship (avoids N+1 queries)

    Use case:
    - Admin dashboard showing review queue
    - Prioritizes oldest submissions (FIFO)

    Scale consideration (from report):
    - At 500+ pending, alert ops for admin capacity
    - At 1000+ pending, circuit breaker engages (503)
    """
    offset = (pagination.page -1) * pagination.limit

    pending = db.query(Contribution).options(
        joinedload(Contribution.user)  # Avoid N+1: Load user in same query
    ).filter(
        Contribution.status == ContributionStatus.PENDING
    ).order_by(
        Contribution.created_at.asc()  # FIFO: Oldest first
    ).offset(offset).limit(pagination.limit).all()

    return pending

@router.post(
    "/verify/{contribution_id}",
    response_model=ContributionResponse,
    summary="Verify or reject submission",
    responses={
        200: {"description": "Verification complete"},
        401: {"description": "Not authenticated"},
        403: {"description": "Admin access required"},
        404: {"description": "Submission not found"},
        422: {"description": "Invalid decision"}
    }
)
async def verify_submission(
    contribution_id: int,
    verification: VerificationRequest,
    admin: AdminUser,
    db: DbSession
):
    """
    Process admin verification decision.

    Flow:
    1. Acquire row lock on contribution (prevents concurrent updates)
    2. Check if already verified (idempotent behavior)
    3. Map decision to status (APPROVE->VERIFIED, REJECT->REJECTED, etc.)
    4. Update contribution status
    5. Create immutable log entry
    6. Commit transaction (both or neither)

    Idempotency:
    - If contribution already processed, return current state
    - No error raised (safe for retry/double-click)
    - Log still created (audit trail of repeated attempts)

    Race condition prevention:
    Scenario: Two admins verify same submission simultaneously

    Without locking:
    T1: Admin A reads status=PENDING
    T2: Admin B reads status=PENDING
    T3: Admin A updates to VERIFIED
    T4: Admin B updates to REJECTED (overwrites!)
    Result: Inconsistent state, lost decision

    With row locking (with_for_update)
    T1: Admin A acquires lock, reads status=PENDING
    T2: Admin B waits for lock...
    T3: Admin A updates to VERIFIED, commits, releases lock
    T4: Admin B acquires lock, reads status=VERIFIED (already done)
    T5: Admin B sees idempotent response, logs duplicate attempt
    Result: First decision wins, both logged

    Transaction guarantees (ACID):
    - Atomicity: Status update + log insert both succeed or both rollback
    - Consistency: No orphaned logs without status change
    - Isolation: Row lock prevents concurrent modifications
    - Durability: Committed changes survive crash

    Decision mapping:
    - APPROVE -> VERIFIED (contribution accepted into asset pool)
    - REJECT -> REJECTED (contribution denied, not visible)
    - REQUEST_CHANGES -> NEEDS_CHANGES (user can resubmit, Phase 2)
    """
    # Acquire row lock to prevent concurrent verification
    # with_for_update() uses SELECT ... FOR UPDATE in SQL
    # Other transactions wait untill this transaction commits/rolls back
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).with_for_update().first()

    if contribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Idempotency check: Already verified?
    if contribution.status != ContributionStatus.PENDING:
        # Already processed - return current state without error
        # Still log this attempt for audit trail
        log_entry = VerificationLog(
            contribution_id=contribution.id,
            admin_id=admin.id,
            decision=verification.decision,
            notes=f"[Duplicate] Already {contribution.status.value}. {verification.notes or ''}"
        )
        db.add(log_entry)
        db.commit()

        return contribution

    # Map verification decision to contribution status
    status_mapping = {
        VerificationDecision.APPROVE: ContributionStatus.VERIFIED,
        VerificationDecision.REJECT: ContributionStatus.REJECTED,
        VerificationDecision.REQUEST_CHANGES: ContributionStatus.NEEDS_CHANGES
    }

    new_status = status_mapping[verification.decision]

    # Transaction: Update status + create log (atomic)
    try:
        # Update contribution status
        contribution.status = new_status

        # Create immutable audit log
        log_entry = VerificationLog(
            contribution_id=contribution.id,
            admin_id=admin.id,
            decision=verification.decision,
            notes=verification.notes
        )
        db.add(log_entry)

        # Commit both changes atomically
        db.commit()
        db.refresh(contribution)

    except Exception as e:
        # Rollback on any error (maintains consistency)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )

    return contribution



