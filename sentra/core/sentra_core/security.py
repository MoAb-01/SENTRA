"""Authentication, RBAC dependencies, bcrypt hashing, and HKDF-SHA256 node key derivation."""

from __future__ import annotations

import hashlib
import secrets
import struct
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sentra_protocol.constants import AES_256_KEY_SIZE, UINT32_MAX
from sentra_protocol.models import UserRole

JWT_ALGORITHM: str = "HS256"
REFRESH_COOKIE_NAME: str = "sentra_refresh_token"
_BEARER_SCHEME = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Verified operator/admin/auditor identity decoded from short-lived Access JWT."""

    user_id: UUID
    email: str
    role: UserRole


def hash_password(plain_password: str) -> str:
    """Hash a password with per-password random bcrypt salt."""
    if not plain_password:
        raise ValueError("Password must not be empty")
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time bcrypt password verification."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def derive_node_key(master_key: bytes, node_id: UUID, key_id: int) -> bytes:
    """Deterministically derive an isolated 256-bit per-node key via HKDF-SHA256.

    Info binding: b"sentra-node-v1-" + uint32_be(key_id), salted with raw 16-byte node_id.
    Eliminates storing raw symmetric keys in PostgreSQL.
    """
    if len(master_key) != AES_256_KEY_SIZE:
        raise ValueError(f"Master KEK must be {AES_256_KEY_SIZE} bytes")
    if not (0 <= key_id <= UINT32_MAX):
        raise ValueError(f"key_id out of uint32 range: {key_id}")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=AES_256_KEY_SIZE,
        salt=node_id.bytes,
        info=b"sentra-node-v1-" + struct.pack("!I", key_id),
    )
    return hkdf.derive(master_key)


def generate_refresh_token() -> tuple[str, str]:
    """Generate a cryptographically random opaque refresh token and its SHA-256 hex digest."""
    raw = secrets.token_urlsafe(48)
    digest = hash_refresh_token(raw)
    return raw, digest


def hash_refresh_token(raw_token: str) -> str:
    """Compute canonical SHA-256 hex digest of an opaque refresh token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    user: AuthenticatedUser,
    *,
    jwt_secret: bytes,
    expire_minutes: int,
) -> str:
    """Mint a short-lived HS256 JWT Access Token (15-60 min)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str, *, jwt_secret: bytes) -> AuthenticatedUser:
    """Validate HS256 JWT Access Token signature, expiry, and claims."""
    try:
        decoded = jwt.decode(token, jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if decoded.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = decoded.get("role")
    if role not in ("ADMIN", "OPERATOR", "AUDITOR"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(str(decoded["sub"]))
        email = str(decoded["email"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedUser(user_id=user_id, email=email, role=role)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_BEARER_SCHEME),
) -> AuthenticatedUser:
    """FastAPI dependency authenticating Bearer JWT Access Tokens."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    jwt_secret: bytes = request.app.state.config.jwt_secret
    return verify_access_token(credentials.credentials, jwt_secret=jwt_secret)


def require_roles(*allowed_roles: UserRole) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """FastAPI RBAC dependency enforcing that the caller holds one of allowed_roles."""
    allowed_set = frozenset(allowed_roles)

    def _check_role(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized for this operation",
            )
        return user

    return _check_role
