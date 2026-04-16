# SQLAlchemy models for Portfolio WebApp
# Railway: Set DATABASE_URL env var for Postgres connection

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Post(Base):
    """Portfolio post model - stores design work with optional media."""
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    media_path = Column(String(500), nullable=True)      # Filesystem path or identifier
    media_type = Column(String(20), nullable=True)       # 'image', 'video', or None
    thumbnail_path = Column(String(500), nullable=True)  # Thumbnail/poster path
    is_draft = Column(Boolean, default=False)
    media_data = Column(LargeBinary, nullable=True)      # For DB storage option
    thumbnail_data = Column(LargeBinary, nullable=True)  # Thumbnail binary
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContactMessage(Base):
    """Contact form submission model."""
    __tablename__ = "contact_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContactInfo(Base):
    """Editable contact information - single row table."""
    __tablename__ = "contact_info"
    
    id = Column(Integer, primary_key=True, default=1)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    social_json = Column(JSON, default=dict)  # {instagram: "...", linkedin: "..."}
    bio = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
