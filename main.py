# Main FastAPI application - Portfolio WebApp Backend
# Deploy to Railway: Set DATABASE_URL, OWNER_PASSWORD, JWT_SECRET (or SECRET_KEY), MEDIA_STORAGE
# Start command: uvicorn main:app --host 0.0.0.0 --port $PORT

import os
import base64
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

# Import local modules
from models import Base
from schemas import (
    AuthRequest, AuthResponse, AuthError,
    PostCreate, PostUpdate, PostResponse, PostList,
    ContactMessageCreate, ContactMessageResponse,
    ContactInfoUpdate, ContactInfoResponse,
    ErrorResponse
)
from auth import verify_owner_password, create_access_token, get_current_user
from crud import (
    create_post, get_post, get_posts, update_post, delete_post,
    create_contact_message, get_contact_info, update_contact_info
)
from media_handler import process_media_upload, get_media_response_data, MEDIA_STORAGE, MEDIA_DIR

# ==================== CONFIGURATION ====================
# Railway environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/portfolio")
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "change-me-in-production")
JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY", "change-me-in-production")
SECRET_KEY = JWT_SECRET  # Backward compatibility for tests and older configs
MEDIA_STORAGE_MODE = os.getenv("MEDIA_STORAGE", "filesystem")

# Convert postgres:// to postgresql+asyncpg:// for SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# ==================== DATABASE SETUP ====================

# Create async engine with Railway-compatible settings
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # Required for Railway's connection handling
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - create tables on startup."""
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: Cleanup
    await engine.dispose()


# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Portfolio WebApp API",
    description="Backend API for graphic designer portfolio with posts, contact, and owner management.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - Allow browser clients from any origin (JWT auth uses Authorization header, not cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ==================== AUTH ENDPOINTS ====================

@app.post("/auth/check", response_model=AuthResponse, responses={401: {"model": AuthError}, 429: {"model": AuthError}})
async def authenticate_owner(auth_data: AuthRequest, request: Request):
    """
    Authenticate owner with password.
    Returns JWT token on success (15min expiry).
    Rate limited: 3 failed attempts = 5min lockout.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    if not verify_owner_password(auth_data.password, client_ip):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    token = create_access_token({"sub": "owner", "role": "admin"})
    return AuthResponse(token=token)


# ==================== POSTS ENDPOINTS ====================

@app.post("/posts", response_model=PostResponse)
async def create_new_post(
    title: str = Form(..., min_length=1, max_length=255),
    description: Optional[str] = Form(None),
    is_draft: bool = Form(False),
    media: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new portfolio post (owner only).
    Supports text-only posts or posts with image/video media.
    Media is processed and thumbnail generated automatically.
    """
    post_data = PostCreate(title=title, description=description, is_draft=is_draft)
    
    # Process media if provided
    media_type = None
    media_path = None
    thumbnail_path = None
    media_data = None
    thumbnail_data = None
    
    if media and media.filename:
        media_type, media_path, thumbnail_path, media_data, thumbnail_data = await process_media_upload(media)
    
    # Create post
    post = await create_post(
        db, post_data, media_type, media_path, thumbnail_path, media_data, thumbnail_data
    )
    
    return post


@app.get("/posts", response_model=PostList)
async def list_posts(
    page: int = 1,
    page_size: int = 12,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get paginated list of posts.
    Public endpoint - only shows published posts.
    Owner sees all posts including drafts when authenticated.
    """
    include_drafts = current_user is not None
    posts, total = await get_posts(db, page=page, page_size=page_size, include_drafts=include_drafts)
    
    pages = (total + page_size - 1) // page_size
    
    return PostList(
        items=posts,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_single_post(post_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single post by ID."""
    post = await get_post(db, post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.is_draft:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return post


@app.put("/posts/{post_id}", response_model=PostResponse)
async def update_existing_post(
    post_id: int,
    post_update: PostUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing post (owner only)."""
    post = await get_post(db, post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    updated = await update_post(db, post, post_update)
    return updated


@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_post(
    post_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a post (owner only)."""
    post = await get_post(db, post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    await delete_post(db, post)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== CONTACT ENDPOINTS ====================

@app.post("/contact", response_model=ContactMessageResponse)
async def submit_contact_message(
    message_data: ContactMessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a contact form message.
    Public endpoint - stores message in database.
    """
    message = await create_contact_message(db, message_data)
    return message


@app.get("/contact-info", response_model=ContactInfoResponse)
async def get_contact_information(db: AsyncSession = Depends(get_db)):
    """
    Get public contact information.
    Returns email, phone, social links, and bio.
    """
    info = await get_contact_info(db)
    return info


@app.put("/contact-info", response_model=ContactInfoResponse)
async def update_contact_information(
    info_update: ContactInfoUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update contact information (owner only)."""
    updated = await update_contact_info(db, info_update)
    return updated


# ==================== MEDIA SERVING ====================

@app.get("/media/{filename:path}")
async def serve_media(filename: str):
    """
    Serve media files with proper content-type and caching.
    Supports both filesystem and DB storage modes.
    """
    # Security: prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    if MEDIA_STORAGE_MODE == "filesystem":
        file_path = MEDIA_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine content type
        content_type = "application/octet-stream"
        if filename.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.endswith(".png"):
            content_type = "image/png"
        elif filename.endswith(".webp"):
            content_type = "image/webp"
        elif filename.endswith(".gif"):
            content_type = "image/gif"
        elif filename.endswith(".mp4"):
            content_type = "video/mp4"
        elif filename.endswith(".webm"):
            content_type = "video/webm"
        
        return FileResponse(
            file_path,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # 24 hours
                "X-Content-Type-Options": "nosniff"
            }
        )
    else:
        # DB storage - files served via API with base64
        # This would require fetching from DB, but for now return 404
        raise HTTPException(status_code=404, detail="File not found in DB mode")


# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway monitoring."""
    return {"status": "healthy", "version": "1.0.0"}


# ==================== ERROR HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler - don't leak internal details."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
