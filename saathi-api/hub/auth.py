"""
hub/auth.py — JWT Authentication Layer for Saathi Cloud Hub

Handles:
- JWT token generation (access + refresh)
- Token validation for both HTTP and WebSocket contexts
- User registration & login with bcrypt password hashing
- Daemon auth via pre-shared keys (PSK)
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env explicitly before fetching secrets
load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "saathi-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
DAEMON_PSK = os.getenv("DAEMON_PSK", "")  # Pre-shared key for daemon auth

# ── In-memory user store (swap for Redis/DB in production) ─────────────────────

_users: dict[str, dict] = {}


# ── Pydantic Models ────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    full_name: str = Field(default="Saathi User")


class UserLogin(BaseModel):
    email: str
    password: str


class TokenPayload(BaseModel):
    sub: str           # user_id or daemon_id
    email: str = ""
    role: str = "user"  # "user" | "daemon"
    exp: float = 0
    iat: float = 0
    jti: str = ""       # unique token id


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ── Password Helpers (direct bcrypt — no passlib) ──────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly (passlib is broken with bcrypt>=4.1)."""
    pw_bytes = password.encode("utf-8")[:72]  # bcrypt max is 72 bytes
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8")[:72],
            hashed.encode("utf-8"),
        )
    except Exception:
        return False


# ── Token Generation ───────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    email: str = "",
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now.timestamp(),
        "exp": expire.timestamp(),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, email: str = "") -> str:
    """Create a long-lived refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "refresh",
        "iat": now.timestamp(),
        "exp": expire.timestamp(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_token_pair(user_id: str, email: str = "", role: str = "user") -> TokenPair:
    """Generate an access + refresh token pair."""
    return TokenPair(
        access_token=create_access_token(user_id, email, role),
        refresh_token=create_refresh_token(user_id, email),
    )


def create_daemon_token(daemon_id: str) -> str:
    """Create a token specifically for a daemon connection."""
    return create_access_token(
        user_id=daemon_id,
        email="",
        role="daemon",
        expires_delta=timedelta(days=365),  # Long-lived for daemons
    )


# ── Token Validation ──────────────────────────────────────────────────────────

def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def validate_access_token(token: str) -> Optional[dict]:
    """Validate an access token and return the payload."""
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return payload
    return None


def validate_daemon_token(token: str) -> Optional[dict]:
    """Validate a daemon's JWT token."""
    payload = decode_token(token)
    if payload and payload.get("role") == "daemon":
        return payload
    return None


def validate_daemon_psk(psk: str) -> bool:
    """Validate a daemon's pre-shared key."""
    if not DAEMON_PSK:
        return False
    return psk == DAEMON_PSK


# ── User Management (In-Memory — Swap for DB) ─────────────────────────────────

def register_user(email: str, password: str, full_name: str = "Saathi User") -> dict:
    """Register a new user. Returns user dict."""
    if email in _users:
        raise ValueError(f"User {email} already exists")

    import uuid
    user_id = str(uuid.uuid4())
    _users[email] = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(password),
        "full_name": full_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"id": user_id, "email": email, "full_name": full_name}


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate a user. Returns user dict or None."""
    user = _users.get(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"], "full_name": user["full_name"]}


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Look up a user by ID."""
    for user in _users.values():
        if user["id"] == user_id:
            return {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
            }
    return None
