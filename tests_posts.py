# Posts API Tests for Portfolio WebApp
# Run with: pytest tests_posts.py -v

import pytest
import io
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


# ==================== PUBLIC ENDPOINTS ====================

@pytest.mark.asyncio
async def test_get_posts_public(client):
    """Test getting posts without authentication."""
    response = await client.get("/posts")
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data


@pytest.mark.asyncio
async def test_get_posts_pagination(client):
    """Test posts pagination."""
    response = await client.get("/posts?page=1&page_size=5")
    
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 5


@pytest.mark.asyncio
async def test_get_single_post_not_found(client):
    """Test getting non-existent post."""
    response = await client.get("/posts/99999")
    
    assert response.status_code == 404


# ==================== PROTECTED ENDPOINTS ====================

@pytest.mark.asyncio
async def test_create_post_text_only(client, auth_headers):
    """Test creating a text-only post."""
    post_data = {
        "title": "Test Post",
        "description": "This is a test post",
        "is_draft": False
    }
    
    response = await client.post(
        "/posts",
        data=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Post"
    assert data["description"] == "This is a test post"
    assert data["is_draft"] is False
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_post_draft(client, auth_headers):
    """Test creating a draft post."""
    post_data = {
        "title": "Draft Post",
        "description": "This is a draft",
        "is_draft": True
    }
    
    response = await client.post(
        "/posts",
        data=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_draft"] is True


@pytest.mark.asyncio
async def test_create_post_unauthorized(client):
    """Test creating post without authentication."""
    response = await client.post(
        "/posts",
        data={"title": "Test"}
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_post_missing_title(client, auth_headers):
    """Test creating post without title."""
    response = await client.post(
        "/posts",
        data={"description": "No title"},
        headers=auth_headers
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_post_with_image(client, auth_headers):
    """Test creating post with image upload."""
    # Create a simple test image
    image_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Minimal PNG header
    
    files = {
        "media": ("test.png", io.BytesIO(image_content), "image/png")
    }
    
    data = {
        "title": "Post with Image",
        "description": "Testing image upload",
        "is_draft": False
    }
    
    response = await client.post(
        "/posts",
        data=data,
        files=files,
        headers=auth_headers
    )
    
    # May fail due to invalid image, but should not be auth error
    assert response.status_code != 401
    assert response.status_code != 403


@pytest.mark.asyncio
async def test_update_post(client, auth_headers):
    """Test updating a post."""
    # First create a post
    create_response = await client.post(
        "/posts",
        data={"title": "Original Title", "is_draft": False},
        headers=auth_headers
    )
    
    if create_response.status_code != 200:
        pytest.skip("Could not create post for update test")
    
    post_id = create_response.json()["id"]
    
    # Update the post
    update_response = await client.put(
        f"/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=auth_headers
    )
    
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_update_post_not_found(client, auth_headers):
    """Test updating non-existent post."""
    response = await client.put(
        "/posts/99999",
        json={"title": "Updated"},
        headers=auth_headers
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_post(client, auth_headers):
    """Test deleting a post."""
    # First create a post
    create_response = await client.post(
        "/posts",
        data={"title": "Post to Delete", "is_draft": False},
        headers=auth_headers
    )
    
    if create_response.status_code != 200:
        pytest.skip("Could not create post for delete test")
    
    post_id = create_response.json()["id"]
    
    # Delete the post
    delete_response = await client.delete(
        f"/posts/{post_id}",
        headers=auth_headers
    )
    
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_delete_post_not_found(client, auth_headers):
    """Test deleting non-existent post."""
    response = await client.delete("/posts/99999", headers=auth_headers)
    
    assert response.status_code == 404


# ==================== DRAFT VISIBILITY ====================

@pytest.mark.asyncio
async def test_draft_not_visible_publicly(client, auth_headers):
    """Test that drafts are not visible without authentication."""
    # Create a draft post
    create_response = await client.post(
        "/posts",
        data={"title": "Secret Draft", "is_draft": True},
        headers=auth_headers
    )
    
    if create_response.status_code != 200:
        pytest.skip("Could not create draft for test")
    
    post_id = create_response.json()["id"]
    
    # Try to get it without auth
    get_response = await client.get(f"/posts/{post_id}")
    
    # Should be 404 (not found) for public users
    assert get_response.status_code == 404


# ==================== MAIN ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
