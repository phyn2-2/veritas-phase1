"""
Manual tests for config, database, auth layers.
Run: python test_bootstrap.py
"""
from app.config import get_settings, Settings
from app.database import engine, get_db
from app.auth import hash_password, verify_password, create_access_token, decode_access_token
import os
from sqlalchemy import text

def test_config():
    """Verify config validation"""
    print("Testing config...")

    # Should fail with short key
    try:
        Settings(
            model_config={"env_file": None},
            SECRET_KEY="short"
        )
        print("FAILED: Short SECRET_KEY accepted")
    except ValueError as e:
        print(f"PASSED: {e}")

    # Should succeed with valid key
    settings = Settings(
        _env__file=None,
        SECRET_KEY="a" * 32,
        DATABASE_URL="sqlite:///./test.db"
    )
    print(f"PASSED: Settings loaded, expire={settings.ACCESS_TOKEN_EXPIRE_MINUTES}min")

def test_database():
    """Verify database connection and FK enforcement"""
    print("\nTesting database...")

    # Connection test
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar_one()
        assert result == 1
        print("PASSED: Database connection successful")

        # FK check
        fk_result = conn.execute(text("PRAGMA foreign_keys")).scalar_one()
        assert fk_result == 1, "Foreign keys not enabled!"
        print("PASSED: Foreign keys enabled")

def test_auth():
    """Verify password hashing and JWT operations"""
    print("\nTesting auth...")

    # Password hashing
    password = "SecureP@ssw0rd123"
    hashed = hash_password(password)
    assert hashed != password, "Password not hashed!"
    assert hashed.startswith("$2b$"), "Not bcrypt hash!"
    print(f"PASSED: Password hashed (bcrypt)")

    # Verification
    assert verify_password(password, hashed) == True
    assert verify_password("wrong", hashed) == False
    print("PASSED: Password Verification works")

    # JWT creation
    token = create_access_token({"sub": "123", "is_admin": False})
    assert isinstance(token, str)
    assert len(token) > 50  # JWT is long
    print(f"PASSED: JWT created ({len(token)} chars)")

    # JWT decode
    payload = decode_access_token(token)
    assert payload["sub"] == "123"
    assert payload["is_admin"] == False
    assert "exp" in payload
    print(f"PASSED: JWT decoded, expires at {payload['exp']}")

    # Invalid token
    assert decode_access_token("invalid.token.here") is None
    print("PASSED: Invalid token rejected")

if __name__ == "__main__":
    test_config()
    test_database()
    test_auth()
    print("\n All bootstrap tests passed!")
