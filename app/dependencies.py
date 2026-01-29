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

