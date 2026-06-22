from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.security import TokenType, create_token, decode_token, hash_password, verify_password


def test_password_hash_round_trip():
    encoded = hash_password("Correct-Horse-42!")
    assert encoded != "Correct-Horse-42!"
    assert verify_password("Correct-Horse-42!", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_is_tenant_scoped():
    user_id, tenant_id = uuid4(), uuid4()
    token = create_token(user_id, tenant_id, "manager", TokenType.ACCESS)
    claims = decode_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["tenant"] == str(tenant_id)
    assert claims["role"] == "manager"


def test_production_rejects_sqlite_and_wildcard_cors():
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            app_secret_key="production-test-secret-with-32-characters",
            database_url="sqlite+aiosqlite:///./unsafe.db",
            cors_origins=["*"],
        )
