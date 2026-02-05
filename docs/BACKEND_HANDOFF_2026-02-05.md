# VERITAS Phase 1 Backend Handoff Document

**Date:** February 5, 2026  
**Status:** ✅ READY FOR FRONTEND INTEGRATION  
**API Version:** `1.0.0`  
**Base URL:** `http://localhost:8000` (development)

---

## 1. SYSTEM STATUS (AUTHORITATIVE)

### Backend Declaration
The VERITAS Phase 1 backend is feature-complete and API-stable. All endpoints have been integration-tested. The contract outlined in this document will not change without explicit versioning.

| In Scope | Out of Scope (Phase 1) |
| :--- | :--- |
| User registration & auth | File upload/storage (Use HTTPS URLs) |
| JWT session management | Contribution editing/resubmission |
| Submission workflow (Pending) | Token refresh mechanism |
| Admin verification | Admin dashboard UI |
| Public asset listing | Rate limiting & Notifications |
| Pagination & Business rules | Search/filtering |

> **Frontend Responsibility:** Do not attempt to work around out-of-scope features. These are intentional phase boundaries.

---

## 2. API SURFACE SUMMARY

### Authentication
| Method | Path | Auth Required | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/register` | No | Create new account |
| `POST` | `/api/login` | No | Authenticate & receive token |

### Submissions
| Method | Path | Auth Required | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/submissions` | Yes | Create new contribution |
| `GET` | `/api/submissions/mine` | Yes | List my submissions |
| `GET` | `/api/submissions/{id}` | Yes | Get specific submission |

### Admin & Public
| Method | Path | Auth Required | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/pending` | Yes (Admin) | List pending submissions |
| `POST` | `/api/admin/verify/{id}`| Yes (Admin) | Approve/reject submission |
| `GET` | `/api/assets` | No | List verified contributions |

---

## 3. AUTHENTICATION CONTRACT

### Token Lifecycle
* **Duration:** Valid for **30 minutes** from issuance.
* **Expiry:** No warning. No refresh. User must re-authenticate.
* **Header Format:** `Authorization: Bearer <access_token>` (Note the space).

### HTTP Status Code Semantics
* **401 Unauthorized:** Token expired or missing. **Action:** Redirect to Login.
* **403 Forbidden:** Valid token, but no permission (e.g., non-admin accessing admin routes). **Action:** Show "Access Denied."

---

## 4. CORE USER FLOWS

### Flow 1: Registration & Login
1. `POST /api/register` → Returns `201 Created`.
2. `POST /api/login` → Returns `200 OK` with `access_token`.
3. **Frontend:** Store token in `localStorage` or `sessionStorage`.

### Flow 2: Submit Contribution
* **Constraints:**
    * Max **3 pending** submissions allowed per user (`409 Conflict`).
    * `file_url` must be **HTTPS** (`422 Unprocessable Entity`).
    * Title: Max 200 chars | Description: Max 10,000 chars.

### Flow 3: Pagination Logic
* Default: `page=1&limit=50`.
* **Frontend:** Determine the "Last Page" when `response.length < limit`.

---

## 5. ERROR HANDLING CONTRACT

All errors follow this canonical shape:
```json
{
  "detail": "Human-readable error message"
}
