"""
Router package initialization.
Exports all routers for app.main registration.
"""
from app.routers import auth, submissions, admin, assets

__all__ = ["auth", "submissions", "admin", "assets"]




