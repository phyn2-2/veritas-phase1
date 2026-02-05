┌─────────────────────────────────────────────────────────────────┐
│                     REQUEST LIFECYCLE                            │
└─────────────────────────────────────────────────────────────────┘

PUBLIC ENDPOINTS (No Auth)
├── GET  /                    → [No dependencies]
├── GET  /api/assets          → [DbSession only]
├── POST /api/register        → [DbSession only]
└── POST /api/login           → [DbSession only]

AUTHENTICATED ENDPOINTS (CurrentUser required)
├── POST /api/submissions     → [DbSession] → [get_current_user]
├── GET  /api/submissions/mine → [DbSession] → [get_current_user]
├── GET  /api/submissions/{id} → [DbSession] → [get_current_user]
└── POST /api/assets/presign   → [DbSession] → [get_current_user]

ADMIN ENDPOINTS (AdminUser required)
├── GET  /api/admin/pending    → [DbSession] → [get_current_user] → [require_admin]
└── POST /api/admin/verify/{id} → [DbSession] → [get_current_user] → [require_admin]

┌─────────────────────────────────────────────────────────────────┐
│                   DEPENDENCY CHAIN DETAILS                       │
└─────────────────────────────────────────────────────────────────┘

1. DbSession (get_db)
   ├── Creates SQLAlchemy session
   ├── Yields session to endpoint
   ├── Auto-commits on success
   └── Auto-rollbacks on exception
   
2. CurrentUser (get_current_user) 
   ├── Depends on: HTTPBearer (extracts token)
   ├── Depends on: DbSession
   ├── Validates JWT signature & expiration
   ├── Queries user from database by token.sub
   ├── Returns User object
   └── Raises 401 if: missing token, invalid token, expired token, user deleted

3. AdminUser (require_admin)
   ├── Depends on: CurrentUser (authentication)
   ├── Checks: current_user.is_admin == True
   ├── Returns User object (same as CurrentUser)
   └── Raises 403 if: user.is_admin == False

DEPENDENCY RESOLUTION ORDER (FastAPI automatic):
AdminUser → CurrentUser → (HTTPBearer + DbSession) → Endpoint
