# Media handling module - file uploads, validation, thumbnails
# Supports both filesystem and database storage (MEDIA_STORAGE env var)

import os
import io
import uuid
import magic
import subprocess
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from PIL import Image, ImageOps
from fastapi import UploadFile, HTTPException, status

# ==================== CONFIGURATION ====================
# Railway: Set MEDIA_STORAGE=filesystem or MEDIA_STORAGE=db
MEDIA_STORAGE = os.getenv("MEDIA_STORAGE", "filesystem")

# Storage paths (container root for Railway)
MEDIA_DIR = Path("/media")
THUMBNAIL_DIR = Path("/media/thumbnails")

# Create directories if using filesystem storage
if MEDIA_STORAGE == "filesystem":
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# ==================== VALIDATION CONFIG ====================

# Allowed MIME types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_MEDIA_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES

# Size limits (bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024      # 10MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024      # 50MB
MAX_THUMBNAIL_SIZE = 2 * 1024 * 1024   # 2MB

# Thumbnail dimensions
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 300


# ==================== VALIDATION ====================

def validate_media_file(file: UploadFile, content: bytes) -> Tuple[str, str]:
    """
    Validate uploaded file - check MIME type and size.
    Returns (media_type, mime_type) or raises HTTPException.
    """
    # Detect MIME type from content (not just filename)
    mime_type = magic.from_buffer(content, mime=True)
    
    # Determine media category
    if mime_type in ALLOWED_IMAGE_TYPES:
        media_type = "image"
        max_size = MAX_IMAGE_SIZE
    elif mime_type in ALLOWED_VIDEO_TYPES:
        media_type = "video"
        max_size = MAX_VIDEO_SIZE
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {mime_type}. Allowed: images (JPEG, PNG, WebP, GIF) and videos (MP4, WebM, MOV)."
        )
    
    # Check file size
    file_size = len(content)
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size for {media_type}s is {max_mb}MB."
        )
    
    return media_type, mime_type


# ==================== THUMBNAIL GENERATION ====================

def generate_image_thumbnail(image_bytes: bytes, filename: str) -> Tuple[bytes, str]:
    """
    Generate thumbnail from image bytes.
    Returns (thumbnail_bytes, thumbnail_filename).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (handles RGBA, P modes)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Use thumbnail method for better quality (preserves aspect ratio)
        img.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=85, method=6)
        output.seek(0)
        
        thumbnail_filename = f"thumb_{uuid.uuid4().hex[:12]}.webp"
        return output.getvalue(), thumbnail_filename
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate thumbnail: {str(e)}"
        )


def generate_video_poster(video_bytes: bytes, filename: str) -> Optional[Tuple[bytes, str]]:
    """
    Generate poster frame from video using ffmpeg.
    Returns (poster_bytes, poster_filename) or None if ffmpeg not available.
    """
    try:
        # Check if ffmpeg is available
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            return None  # ffmpeg not available
        
        # Create temp files
        video_id = uuid.uuid4().hex[:12]
        temp_video = f"/tmp/{video_id}_{filename}"
        temp_poster = f"/tmp/{video_id}_poster.jpg"
        
        # Write video to temp file
        with open(temp_video, "wb") as f:
            f.write(video_bytes)
        
        # Extract frame at 1 second using ffmpeg
        subprocess.run([
            "ffmpeg", "-i", temp_video,
            "-ss", "00:00:01.000",
            "-vframes", "1",
            "-q:v", "2",
            "-y",  # Overwrite output
            temp_poster
        ], capture_output=True, timeout=30, check=True)
        
        # Read poster
        with open(temp_poster, "rb") as f:
            poster_bytes = f.read()
        
        # Generate thumbnail from poster
        thumb_bytes, thumb_filename = generate_image_thumbnail(poster_bytes, "poster.jpg")
        
        # Cleanup
        os.remove(temp_video)
        os.remove(temp_poster)
        
        return thumb_bytes, thumb_filename
        
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg failed or not available - return None, will use fallback
        return None
    except Exception as e:
        # Cleanup on error
        try:
            os.remove(temp_video)
            os.remove(temp_poster)
        except:
            pass
        return None


# ==================== STORAGE ====================

class MediaStorage:
    """Abstract media storage - handles both filesystem and DB storage."""
    
    @staticmethod
    def save_file(content: bytes, filename: str, is_thumbnail: bool = False) -> str:
        """
        Save file to storage. Returns path/identifier.
        For filesystem: returns relative path
        For DB: returns UUID identifier (content stored separately)
        """
        if MEDIA_STORAGE == "filesystem":
            return MediaStorage._save_to_filesystem(content, filename, is_thumbnail)
        else:
            return MediaStorage._save_to_db_reference(filename, is_thumbnail)
    
    @staticmethod
    def _save_to_filesystem(content: bytes, filename: str, is_thumbnail: bool) -> str:
        """Save file to filesystem."""
        target_dir = THUMBNAIL_DIR if is_thumbnail else MEDIA_DIR
        filepath = target_dir / filename
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        # Return relative path for URL construction
        if is_thumbnail:
            return f"thumbnails/{filename}"
        return filename
    
    @staticmethod
    def _save_to_db_reference(filename: str, is_thumbnail: bool) -> str:
        """Generate DB reference identifier."""
        prefix = "thumb_" if is_thumbnail else "media_"
        return f"{prefix}{uuid.uuid4().hex[:16]}"
    
    @staticmethod
    def delete_file(filepath: str) -> bool:
        """Delete file from storage. Returns success status."""
        if MEDIA_STORAGE == "filesystem" and filepath:
            try:
                full_path = MEDIA_DIR / filepath
                if full_path.exists():
                    full_path.unlink()
                    return True
            except Exception:
                pass
        return False


# ==================== MAIN HANDLER ====================

async def process_media_upload(file: UploadFile) -> Tuple[str, str, Optional[str], Optional[bytes], Optional[bytes]]:
    """
    Process uploaded media file - validate, generate thumbnail, save.
    
    Returns:
        - media_type: 'image' or 'video'
        - media_path: path/identifier for the media
        - thumbnail_path: path/identifier for thumbnail (or None)
        - media_data: binary data for DB storage (or None for filesystem)
        - thumbnail_data: binary thumbnail data for DB storage (or None)
    """
    # Read file content
    content = await file.read()
    await file.seek(0)
    
    # Validate
    media_type, mime_type = validate_media_file(file, content)
    
    # Generate unique filename
    file_ext = Path(file.filename or "unknown").suffix.lower()
    if media_type == "image" and mime_type == "image/webp":
        file_ext = ".webp"
    media_filename = f"{uuid.uuid4().hex[:16]}{file_ext}"
    
    thumbnail_path = None
    thumbnail_data = None
    
    # Generate thumbnail/poster
    if media_type == "image":
        thumb_bytes, thumb_filename = generate_image_thumbnail(content, media_filename)
        thumbnail_path = MediaStorage.save_file(thumb_bytes, thumb_filename, is_thumbnail=True)
        if MEDIA_STORAGE == "db":
            thumbnail_data = thumb_bytes
    
    elif media_type == "video":
        poster_result = generate_video_poster(content, media_filename)
        if poster_result:
            thumb_bytes, thumb_filename = poster_result
            thumbnail_path = MediaStorage.save_file(thumb_bytes, thumb_filename, is_thumbnail=True)
            if MEDIA_STORAGE == "db":
                thumbnail_data = thumb_bytes
    
    # Save main media
    media_path = MediaStorage.save_file(content, media_filename, is_thumbnail=False)
    media_data = content if MEDIA_STORAGE == "db" else None
    
    return media_type, media_path, thumbnail_path, media_data, thumbnail_data


def get_media_response_data(post) -> dict:
    """
    Get media data for API response.
    For filesystem: returns URLs
    For DB: returns base64 data URLs
    """
    import base64
    
    result = {
        "media_url": None,
        "thumbnail_url": None
    }
    
    if MEDIA_STORAGE == "filesystem":
        if post.media_path:
            result["media_url"] = f"/media/{post.media_path}"
        if post.thumbnail_path:
            result["thumbnail_url"] = f"/media/{post.thumbnail_path}"
    else:
        # DB storage - return data URLs
        if post.media_data:
            mime = "image/jpeg" if post.media_type == "image" else "video/mp4"
            b64 = base64.b64encode(post.media_data).decode()
            result["media_url"] = f"data:{mime};base64,{b64}"
        if post.thumbnail_data:
            b64 = base64.b64encode(post.thumbnail_data).decode()
            result["thumbnail_url"] = f"data:image/webp;base64,{b64}"
    
    return result
