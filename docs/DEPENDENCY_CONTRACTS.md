# Dependency Contracts

## get_db
- **Provides:** SQLAlchemy Session
- **Lifetime:** Single HTTP request
- **Guarantees:** Auto-commit on success, auto-rollback on error, always closed
- **Failures:** 500 on database errors

## get_current_user
- **Requires:** Authorization: Bearer <token>
- **Provides:** User object (from database)
- **Guarantees:** Token validated, user exists, permissions fresh
- **Failures:** 401 on auth failures

## require_admin
- **Requires:** Valid authentication
- **Provides:** User object with is_admin=True
- **Guarantees:** Database is source of truth (not token)
- **Failures:** 403 if not admin, 401 if not authenticated

## Security Properties
- Timing-safe login (dummy password hashing)
- Constant-time JWT validation
- No token claim trust (database verification)
- Row-level locking for concurrency safety
```

---

## 10. Success Criteria Verification

✅ **No endpoint can bypass dependency enforcement**
- All protected endpoints use `CurrentUser` or `AdminUser`
- HTTPBearer auto_error=True prevents missing tokens
- No manual token extraction in routers

✅ **All failure modes return deterministic HTTP codes**
- 401: Authentication failures
- 403: Authorization failures (admin required)
- 404: Resource not found
- 409: Conflict (pending limit, duplicate user)
- 422: Validation failures
- 500: Server errors (database, unexpected)

✅ **System remains correct under repeated/malicious requests**
- Idempotent verification (double-approve safe)
- Race-condition safe pending limit (row locking)
- Timing-safe login (no user enumeration)
- Malformed token handling (401, not 500)

**Phase 1 hardening complete. System ready for integration testing.**
