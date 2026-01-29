"""
SQLAlchemy ORM models for Phase 1
Design principles:
1. Explicit constraints prevents invalid states at DB level
2. Enums enforce finite statess machines
3. Relationships use lazy loading (query optimization deferred to Phase 2)
4. Timestamps track audit trail
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone
import enum
from app.database import Base

# ======================================
# ENUMS - Finite State Machines
# ======================================

class ContributionType(str, enum.Enum):
    """
    Type of contribution submitted.
    Why str subclass: Serializes to JSON directly (FastAPI compatibility).
    Stored as VARCHAR in SQLite (readable in DB browser).
    """
    IDEA = "idea"
    WORK = "work"
    ASSET = "asset"

class ContributionStatus(str, enum.Enum):
    """
    Contribution lifecycle states.
    Valid transitions (enforced in business logic, not DB):
    - PENDING -> VERIFIED (admin approves)
    - PENDING -> REJECTED (admin rejects)
    - PENDING -> NEEDS_CHANGES (admin requests revision)

    No transitions FROM verified/rejected (immutable once decided).
    No DRAFT state
    """
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NEEDS_CHANGES = "NEEDS_CHANGES"

class VerificationDecision(str, enum.Enum):
    """
    Admin decision type in verification logs.
    Maps to ContributionStatus:
    - APPROVE -> VERIFIED
    - REJECT -> REJECTED
    -REQUEST_CHANGES -> NEEDS_CHANGES

    Why separate enum: Logs capture intent (verb), status captures state (noun).
    """
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


# ==================
# MODELS
# ==================

class User(Base):
    """
    User accounts with role-based access.
    Constraints:
    - email: Unique, required, indexed for login lookups
    - username: Unique, required, indexed for login lookups
    - password_hash: Required, never expose in API responses
    - is_admin: Defaults to False (least privilege principle)

    Failure modes:
    - Duplicate email/username ->SQLAlchemy IntegrityError (catch in endpoint)
    - Missing password_hash -> NOT NULL constraint violation (prevent at creation)
    - Deleted user with contributions -> Handled by FK nullable=False + application logic
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # Optimize login queries
        comment="User email, must be unique"
    )
    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,  # Optimize login queries
        comment="Display name, must be unique"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hash, never return in API"
    )
    is_admin = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Admin role for verification permissions"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Account creation timestamp (UTC)"
    )

    # Relationships
    contributions = relationship(
        "Contribution",
        back_populates="user",
        lazy="select",  # Load on-demand (N+1 acceptable for Phase 1)
        cascade="none"  # No cascade delete (Section 9: orphan handling)
    )
    verification_logs = relationship(
        "VerificationLog",
        back_populates="admin",
        lazy="select",
        foreign_keys="VerificationLog.admin_id"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, is_admin={self.is_admin})>"

class Contribution(Base):
    """
    User-submitted contributions awaiting or completed verification.
    Constraints:
    - user_id: FK to users, NOT NULL (orphan prevention)
    - title: Required, max 200 chars (UI/UX constraint)
    - description: Required, TEXT type (max ~64KB in SQLite)
    - type: Enum, required
    - file_url: Optional, max 500 chars (URL length limit)
    - status: Enum, defaults to PENDING

    Indexes:
    - user_id: Optimize "my submissions" queries
    - status: Optimize admin pending list + asset queries
    - (status, created_at): Composite for paginated sorted lists

    Failure modes:
    - Invalid user_id -> FK constraint violation (prevent at creation)
    - NULL title/description -> NOT NULL violation (validate in Pydantic)
    - Oversized description -> SQLite TEXT limit (~64KB, check at app layer)
    - Invalid status transition -> Handle in verification service logic
    - Concurrent status updates -> Row-level locking in transaction
    """
    __tablename__ = "contributions"
    __table_args__= (
        Index("ix_contributions_status_created_at", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),  # Prevent user deletion with contributions
        nullable=False,
        index=True,
        comment="Owner of the contribution"
    )
    title = Column(
        String(200),
        nullable=False,
        comment="Contribution title, max 200 chars"
    )
    description = Column(
        Text,  # ~64KB max in SQLite
        nullable=False,
        comment="Detailed description of contribution"
    )
    type = Column(
        Enum(ContributionType, name="contribution_type_enum"),
        nullable=False,
        comment="Category: idea, work or asset"
    )
    file_url = Column(
        String(500),  # URLs can be long (max 2083 in IE, but 500 is reasonable)
        nullable=True,
        comment="Optional external file URL (HTTPS only, validate in Pydantic)"
    )
    status = Column(
        Enum(ContributionStatus, name="contribution_status_enum"),
        default=ContributionStatus.PENDING,
        nullable=False,
        index=True,  # Critical for filtering
        comment="Current state in verification workflow"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,  # Optimize time-based queries
        comment="Submission timestamp (UTC)"
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Last modification timestamp (UTC)"
    )

    # Relationships
    user = relationship(
        "User",
        back_populates="contributions",
        lazy="joined"  # Always load user with contribution (avoid N+1)
    )
    verification_logs = relationship(
        "VerificationLog",
        back_populates="contribution",
        lazy="select",
        cascade="all, delete-orphan"  # Logs deleted if contribution deleted
    )

    def __repr__(self):
        return f"<Contribution(id={self.id}, user_id={self.user_id}, status={self.status.value})>"

class VerificationLog(Base):
    """
    Immutable audit trail of admin verification decisions.
    Why immutable: Once logged, never updated/deleted (append-only log)
    Enables reconstruction of decision history.

    Constraints:
    - contribution_id: FK, NOT NULL
    - admin_id: FK, NOT NULL (admin cannot be deleted while logs exist)
    - decision: Enum, required
    - notes: Optional (admin may provide feedback)
    - Timestamp: Auto-generated, indexed for audit queries

    Failure modes:
    - Orphaned log (contribution deleted) -> Cascade delete handles
    - Invalid admin_id -> FK violation (prevent at creation)
    - Missing decision -> NOT NULL violation (validate in Pydantic)
    - Concurrent logs for same contribution -> Allowed (multiple reviews possible)
    """
    __tablename__ = "verification_logs"

    id = Column(Integer, primary_key=True, index=True)
    contribution_id = Column(
        Integer,
        ForeignKey("contributions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Contribution being verified"
    )
    admin_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),  # prevent admin deletion
        nullable=False,
        index=True,
        comment="Admin who made the decision"
    )
    decision = Column(
        Enum(VerificationDecision, name="verification_decision_enum"),
        nullable=False,
        comment="Admin decision: APPROVE, REJECT, or REQUEST_CHANGES"
    )
    notes = Column(
        Text,
        nullable=True,
        comment="Optional feedback from admin"
    )
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When decision was made (UTC)"
    )

    # Relationships
    contribution = relationship(
        "Contribution",
        back_populates="verification_logs",
    )
    admin = relationship(
        "User",
        back_populates="verification_logs",
        foreign_keys=[admin_id],
        lazy="joined"  # Always load admin info for audit trails
    )

    def __repr__(self):
        return f"<VerificationLog(id={self.id}, contribution_id={self.contribution_id}, decision={self.decision.value})>"






