"""
One-time script to create first admin user.
Usage:
    python scripts/bootstrap_admin.py admin@example.com AdminUser
SecurePassword123

Security:
- Password must meet validation rules (8+ chars, mixed case, digit)
- Hashed before storage (never plaintext)
- Run once, then delete credentials from shell history
"""
import sys
from app.database import SessionLocal
from app.models import User
from app.auth import hash_password
from app.schemas import UserCreate

def create_admin(email: str, username: str, password: str):
    """Create admin user validation"""
    # Validate via Pydantic
    try:
        user_data = UserCreate(email=email, username=username, password=password)
    except Exception as e:
        print(f"Validation failed: {e}")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check if user exists
        existing = db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()

        if existing:
            print(f"User already exists: {existing.email}")
            sys.exit(1)

        # Create admin
        admin = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=hash_password(user_data.password),
            is_admin=True
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"Admin created: {admin.username} (ID: {admin.id})")
        print(f"    Email: {admin.email}")
        print(f"    Admin: {admin.is_admin}")

    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/bootstrap_admin.py <email> <username> <password>")
        sys.exit(1)

    create_admin(sys.argv[1], sys.argv[2], sys.argv[3])

