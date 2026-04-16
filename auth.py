# Authentication module - JWT tokens and password verification
# Railway: Set JWT_SECRET (or SECRET_KEY for backward compatibility) and OWNER_PASSWORD env vars

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ==================== CONFIGURATION ====================
# Get from Railway env vars - NEVER hardcode secrets!
JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "admin123")  # CHANGE THIS!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# ==================== RATE LIMITING ====================
# Simple in-memory rate limiting for auth attempts
_auth_attempts: Dict[str, Dict] = {}  # IP -> {count, last_attempt, locked_until}
MAX_ATTEMPTS = 3
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes


def _get_client_ip() -> str:
    """Get client IP for rate limiting (simplified)."""
    # In production, extract from request headers
    return "default"


def check_rate_limit(client_ip: str) -> None:
    """Check if client is rate limited. Raises HTTPException if locked out."""
    now = time.time()
    
    if client_ip not in _auth_attempts:
        _auth_attempts[client_ip] = {"count": 0, "last_attempt": 0, "locked_until": 0}
    
    attempt = _auth_attempts[client_ip]
    
    # Check if currently locked out
    if attempt["locked_until"] > now:
        remaining = int(attempt["locked_until"] - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {remaining} seconds."
        )
    
    # Reset counter if enough time passed since last attempt
    if now - attempt["last_attempt"] > LOCKOUT_DURATION_SECONDS:
        attempt["count"] = 0


def record_auth_attempt(client_ip: str, success: bool) -> None:
    """Record authentication attempt. Locks out after MAX_ATTEMPTS failures."""
    now = time.time()
    attempt = _auth_attempts.get(client_ip, {"count": 0, "last_attempt": 0, "locked_until": 0})
    
    attempt["last_attempt"] = now
    
    if success:
        attempt["count"] = 0
        attempt["locked_until"] = 0
    else:
        attempt["count"] += 1
        if attempt["count"] >= MAX_ATTEMPTS:
            attempt["locked_until"] = now + LOCKOUT_DURATION_SECONDS
    
    _auth_attempts[client_ip] = attempt


# ==================== PASSWORD VERIFICATION ====================

def verify_owner_password(password: str, client_ip: str = "default") -> bool:
    """
    Verify owner password against OWNER_PASSWORD env var.
    Implements rate limiting - locks out after 3 failed attempts.
    """
    check_rate_limit(client_ip)
    
    # Constant-time comparison to prevent timing attacks
    import hmac
    is_valid = hmac.compare_digest(password.encode(), OWNER_PASSWORD.encode())
    
    record_auth_attempt(client_ip, is_valid)
    return is_valid


# ==================== JWT TOKENS ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with expiration."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ==================== FASTAPI DEPENDENCY ====================

security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    FastAPI dependency to validate JWT token and return user info.
    Use this to protect owner-only routes.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(credentials.credentials)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


# Optional auth - returns user info if valid token, None otherwise
async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """Optional authentication - returns None if no valid token."""
    if not credentials:
        return None
    
    payload = decode_token(credentials.credentials)
    if payload and payload.get("type") == "access":
        return payload
    return None
