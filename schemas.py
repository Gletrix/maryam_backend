# Pydantic schemas for request/response validation
# Used by FastAPI endpoints for type safety and auto-generated docs

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


# ==================== AUTH SCHEMAS ====================

class AuthRequest(BaseModel):
    """Owner authentication request."""
    password: str = Field(..., min_length=1, description="Owner password from OWNER_PASSWORD env var")


class AuthResponse(BaseModel):
    """Successful authentication response with JWT token."""
    token: str
    token_type: str = "bearer"


class AuthError(BaseModel):
    """Authentication error response."""
    detail: str


# ==================== POST SCHEMAS ====================

class PostBase(BaseModel):
    """Base post schema with common fields."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_draft: bool = False


class PostCreate(PostBase):
    """Schema for creating a new post."""
    pass


class PostUpdate(BaseModel):
    """Schema for updating an existing post."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_draft: Optional[bool] = None


class PostResponse(PostBase):
    """Post response schema - includes all fields."""
    id: int
    media_path: Optional[str] = None
    media_type: Optional[str] = None
    thumbnail_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PostList(BaseModel):
    """Paginated list of posts."""
    items: List[PostResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ==================== CONTACT SCHEMAS ====================

class ContactMessageCreate(BaseModel):
    """Schema for submitting a contact message."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    message: str = Field(..., min_length=1, max_length=5000)


class ContactMessageResponse(ContactMessageCreate):
    """Contact message response with metadata."""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ContactInfoBase(BaseModel):
    """Base contact info schema."""
    email: Optional[str] = None
    phone: Optional[str] = None
    social_json: Dict[str, Any] = Field(default_factory=dict)
    bio: Optional[str] = None


class ContactInfoCreate(ContactInfoBase):
    """Schema for creating contact info."""
    pass


class ContactInfoUpdate(BaseModel):
    """Schema for updating contact info."""
    email: Optional[str] = None
    phone: Optional[str] = None
    social_json: Optional[Dict[str, Any]] = None
    bio: Optional[str] = None


class ContactInfoResponse(ContactInfoBase):
    """Contact info response schema."""
    id: int
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== ERROR SCHEMAS ====================

class ErrorResponse(BaseModel):
    """Generic error response."""
    detail: str


class ValidationError(BaseModel):
    """Validation error with field details."""
    detail: List[Dict[str, Any]]
