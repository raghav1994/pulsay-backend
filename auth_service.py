"""
Simple JWT-based auth for Pulsay.
Users are stored in memory — swap _users dict for a real DB when ready.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

SECRET_KEY = os.getenv("JWT_SECRET", "pulsay-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

bearer_scheme = HTTPBearer(auto_error=False)

# In-memory user store: {email: {email, hashed_password, name, created_at}}
_users: dict[str, dict] = {}


def _hash_password(plain: str) -> str:
    """PBKDF2-SHA256 with random salt — stdlib only, no extra deps."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000).hex()
    return f"{salt}:{key}"


def _verify_password(plain: str, stored: str) -> bool:
    try:
        salt, key = stored.split(":", 1)
        test = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000).hex()
        return hmac.compare_digest(test, key)
    except Exception:
        return False


def _create_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def register_user(email: str, password: str, name: str) -> dict:
    email = email.strip().lower()
    if email in _users:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    _users[email] = {
        "email": email,
        "name": name.strip(),
        "hashed_password": _hash_password(password),
        "created_at": datetime.utcnow().isoformat(),
    }
    token = _create_token(email)
    return {"token": token, "user": {"email": email, "name": name.strip()}}


def login_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    user = _users.get(email)
    if not user or not _verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = _create_token(email)
    return {"token": token, "user": {"email": email, "name": user["name"]}}


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency — decodes JWT and returns the user dict."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub", "")
        user = _users.get(email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found.")
        return {"email": user["email"], "name": user["name"]}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired.",
        )
