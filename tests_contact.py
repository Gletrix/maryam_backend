# Contact API Tests for Portfolio WebApp
# Run with: pytest tests_contact.py -v

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from auth import create_access_token


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
def auth_headers():
    """Generate auth headers with valid token."""
    token = create_access_token({"sub": "owner", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


# ==================== CONTACT FORM TESTS ====================

@pytest.mark.asyncio
async def test_submit_contact_message(client):
    """Test submitting a contact message."""
    message_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "message": "Hello, I love your work!"
    }
    
    response = await client.post("/contact", json=message_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["message"] == "Hello, I love your work!"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_submit_contact_missing_name(client):
    """Test submitting contact without name."""
    message_data = {
        "email": "john@example.com",
        "message": "Hello!"
    }
    
    response = await client.post("/contact", json=message_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_contact_missing_email(client):
    """Test submitting contact without email."""
    message_data = {
        "name": "John Doe",
        "message": "Hello!"
    }
    
    response = await client.post("/contact", json=message_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_contact_invalid_email(client):
    """Test submitting contact with invalid email."""
    message_data = {
        "name": "John Doe",
        "email": "not-an-email",
        "message": "Hello!"
    }
    
    response = await client.post("/contact", json=message_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_contact_missing_message(client):
    """Test submitting contact without message."""
    message_data = {
        "name": "John Doe",
        "email": "john@example.com"
    }
    
    response = await client.post("/contact", json=message_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_contact_empty_message(client):
    """Test submitting contact with empty message."""
    message_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "message": ""
    }
    
    response = await client.post("/contact", json=message_data)
    
    assert response.status_code == 422  # Validation error


# ==================== CONTACT INFO TESTS ====================

@pytest.mark.asyncio
async def test_get_contact_info_public(client):
    """Test getting contact info without authentication."""
    response = await client.get("/contact-info")
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert "phone" in data
    assert "social_json" in data
    assert "bio" in data


@pytest.mark.asyncio
async def test_update_contact_info_authorized(client, auth_headers):
    """Test updating contact info with authentication."""
    update_data = {
        "email": "newemail@example.com",
        "phone": "+1234567890",
        "bio": "Updated bio text",
        "social_json": {
            "instagram": "https://instagram.com/test",
            "linkedin": "https://linkedin.com/in/test"
        }
    }
    
    response = await client.put(
        "/contact-info",
        json=update_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newemail@example.com"
    assert data["phone"] == "+1234567890"
    assert data["bio"] == "Updated bio text"
    assert data["social_json"]["instagram"] == "https://instagram.com/test"


@pytest.mark.asyncio
async def test_update_contact_info_unauthorized(client):
    """Test updating contact info without authentication."""
    update_data = {"email": "hacker@example.com"}
    
    response = await client.put("/contact-info", json=update_data)
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_contact_info_partial(client, auth_headers):
    """Test partial update of contact info."""
    # First get current info
    get_response = await client.get("/contact-info")
    original = get_response.json()
    
    # Update only email
    response = await client.put(
        "/contact-info",
        json={"email": "partial@example.com"},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "partial@example.com"
    # Other fields should remain
    assert "phone" in data


@pytest.mark.asyncio
async def test_update_contact_info_invalid_email(client, auth_headers):
    """Test updating contact info with invalid email format."""
    # Note: The schema allows any string for email, not strictly validated
    # This test documents current behavior
    response = await client.put(
        "/contact-info",
        json={"email": "not-an-email"},
        headers=auth_headers
    )
    
    # Currently accepts any string, may want to add validation
    assert response.status_code == 200


# ==================== INTEGRATION TESTS ====================

@pytest.mark.asyncio
async def test_contact_workflow(client, auth_headers):
    """Test complete contact workflow."""
    # 1. Get initial contact info
    get_response = await client.get("/contact-info")
    assert get_response.status_code == 200
    initial_info = get_response.json()
    
    # 2. Update contact info
    update_response = await client.put(
        "/contact-info",
        json={
            "email": "workflow@test.com",
            "phone": "555-0123",
            "bio": "Workflow test bio"
        },
        headers=auth_headers
    )
    assert update_response.status_code == 200
    
    # 3. Verify update
    get_response2 = await client.get("/contact-info")
    assert get_response2.status_code == 200
    updated_info = get_response2.json()
    assert updated_info["email"] == "workflow@test.com"
    assert updated_info["phone"] == "555-0123"
    
    # 4. Submit contact message
    message_response = await client.post("/contact", json={
        "name": "Workflow Tester",
        "email": "tester@example.com",
        "message": "Testing the contact workflow"
    })
    assert message_response.status_code == 200


# ==================== MAIN ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
