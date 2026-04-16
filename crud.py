# CRUD operations for database models
# Uses SQLAlchemy async session for PostgreSQL operations

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from models import Post, ContactMessage, ContactInfo
from schemas import PostCreate, PostUpdate, ContactMessageCreate, ContactInfoUpdate


# ==================== POST CRUD ====================

async def create_post(
    db: AsyncSession,
    post_data: PostCreate,
    media_type: Optional[str] = None,
    media_path: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
    media_data: Optional[bytes] = None,
    thumbnail_data: Optional[bytes] = None
) -> Post:
    """Create a new portfolio post with optional media."""
    db_post = Post(
        title=post_data.title,
        description=post_data.description,
        media_width=post_data.media_width,
        media_height=post_data.media_height,
        is_draft=post_data.is_draft,
        media_type=media_type,
        media_path=media_path,
        thumbnail_path=thumbnail_path,
        media_data=media_data,
        thumbnail_data=thumbnail_data
    )
    
    db.add(db_post)
    await db.commit()
    await db.refresh(db_post)
    return db_post


async def get_post(db: AsyncSession, post_id: int) -> Optional[Post]:
    """Get a single post by ID."""
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    return result.scalar_one_or_none()


async def get_posts(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 12,
    include_drafts: bool = False
) -> tuple[List[Post], int]:
    """
    Get paginated list of posts.
    Returns (posts_list, total_count).
    """
    # Build query
    query = select(Post)
    
    # Filter drafts unless requested
    if not include_drafts:
        query = query.where(Post.is_draft == False)
    
    # Order by creation date (newest first)
    query = query.order_by(desc(Post.created_at))
    
    # Get total count
    count_query = select(func.count(Post.id))
    if not include_drafts:
        count_query = count_query.where(Post.is_draft == False)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    posts = result.scalars().all()
    
    return list(posts), total


async def update_post(
    db: AsyncSession,
    post: Post,
    post_update: PostUpdate
) -> Post:
    """Update an existing post."""
    update_data = post_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(post, field, value)
    
    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post: Post) -> None:
    """Delete a post from the database."""
    await db.delete(post)
    await db.commit()


# ==================== CONTACT MESSAGE CRUD ====================

async def create_contact_message(
    db: AsyncSession,
    message_data: ContactMessageCreate
) -> ContactMessage:
    """Store a new contact form submission."""
    db_message = ContactMessage(
        name=message_data.name,
        email=message_data.email,
        message=message_data.message
    )
    
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message


async def get_contact_messages(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20
) -> tuple[List[ContactMessage], int]:
    """Get paginated list of contact messages (for admin)."""
    query = select(ContactMessage).order_by(desc(ContactMessage.created_at))
    
    # Get total
    total_result = await db.execute(select(func.count(ContactMessage.id)))
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return list(messages), total


# ==================== CONTACT INFO CRUD ====================

async def get_contact_info(db: AsyncSession) -> ContactInfo:
    """Get contact info (creates default if not exists)."""
    result = await db.execute(
        select(ContactInfo).where(ContactInfo.id == 1)
    )
    info = result.scalar_one_or_none()
    
    if info is None:
        # Create default
        info = ContactInfo(
            id=1,
            email="designer@example.com",
            phone="",
            social_json={},
            bio="Graphic designer passionate about visual storytelling."
        )
        db.add(info)
        await db.commit()
        await db.refresh(info)
    
    return info


async def update_contact_info(
    db: AsyncSession,
    info_update: ContactInfoUpdate
) -> ContactInfo:
    """Update contact information."""
    info = await get_contact_info(db)
    
    update_data = info_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(info, field, value)
    
    await db.commit()
    await db.refresh(info)
    return info
