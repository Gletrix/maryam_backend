# Authentication Tests for Portfolio WebApp
# Run with: pytest tests_auth.py -v
# Requires: Backend running or use test database

import pytest
import asyncio
import jwt
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport

# Import the FastAPI app
from main import app, SECRET_KEY, OWNER_PASSWORD
from auth import create_access_token, decode_token, verify_owner_password


# ==================== FIXTURES ====================

@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def valid_token():
    """Generate a valid JWT token for testing."""
    return create_access_token({"sub": "owner", "role": "admin"})


# ==================== TOKEN TESTS ====================

def test_create_access_token():
    """Test JWT token creation."""
    token = create_access_token({"sub": "owner"})
    assert token is not None
    assert isinstance(token, str)
    
    # Decode and verify
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == "owner"
    assert "exp" in payload
    assert "iat" in payload
    assert payload["type"] == "access"


def test_decode_valid_token():
    """Test decoding a valid token."""
    token = create_access_token({"sub": "owner"})
    payload = decode_token(token)
    
    assert payload is not None
    assert payload["sub"] == "owner"


def test_decode_invalid_token():
    """Test decoding an invalid token."""
    payload = decode_token("invalid.token.here")
    assert payload is None


def test_decode_expired_token():
    """Test decoding an expired token."""
    # Create token that expired 1 hour ago
    expired_token = jwt.encode(
        {
            "sub": "owner",
            "exp": datetime.utcnow() - timedelta(hours=1),
            "type": "access"
        },
        SECRET_KEY,
        algorithm="HS256"
    )
    
    payload = decode_token(expired_token)
    assert payload is None


# ==================== PASSWORD TESTS ====================

def test_verify_correct_password():
    """Test password verification with correct password."""
    # Reset rate limit for test
    import auth
    auth._auth_attempts = {}
    
    result = verify_owner_password(OWNER_PASSWORD, "test_client")
    assert result is True


def test_verify_incorrect_password():
    """Test password verification with incorrect password."""
    # Reset rate limit for test
    import auth
    auth._auth_attempts = {}
    
    result = verify_owner_password("wrong_password", "test_client_2")
    assert result is False


# ==================== API ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_auth_check_success(client):
    """Test successful authentication."""
    response = await client.post("/auth/check", json={"password": OWNER_PASSWORD})
    
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_auth_check_wrong_password(client):
    """Test authentication with wrong password."""
    # Use unique client identifier to avoid rate limit from previous tests
    response = await client.post("/auth/check", json={"password": "wrong_password"})
    
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_auth_check_missing_password(client):
    """Test authentication with missing password."""
    response = await client.post("/auth/check", json={})
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_auth_rate_limiting(client):
    """Test rate limiting after multiple failed attempts."""
    # Reset rate limits
    import auth
    auth._auth_attempts = {}
    
    # Make 3 failed attempts
    for i in range(3):
        response = await client.post("/auth/check", json={"password": "wrong_password"})
        assert response.status_code == 401
    
    # 4th attempt should be rate limited
    response = await client.post("/auth/check", json={"password": "wrong_password"})
    assert response.status_code == 429
    data = response.json()
    assert "Too many" in data["detail"] or "Try again" in data["detail"]


@pytest.mark.asyncio
async def test_protected_route_without_token(client):
    """Test accessing protected route without token."""
    response = await client.post("/posts", data={"title": "Test"})
    
    assert response.status_code == 403  # No credentials


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(client):
    """Test accessing protected route with invalid token."""
    response = await client.post(
        "/posts",
        data={"title": "Test"},
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client, valid_token):
    """Test accessing protected route with valid token."""
    # Note: This will fail validation because form data is incomplete,
    # but it should pass auth check first
    response = await client.post(
        "/posts",
        data={"title": ""},  # Empty title will fail validation
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    # Should be 422 (validation error), not 401 (auth error)
    assert response.status_code != 401


# ==================== HEALTH CHECK ====================

@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


# ==================== MAIN ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
