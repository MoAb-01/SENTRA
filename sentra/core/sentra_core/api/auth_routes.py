"""Dual-Token authentication routes: login, silent refresh rotation, logout, and admin revoke."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..config import CoreConfig
from ..repositories.audit_repo import AuditRepository
from ..repositories.auth_repo import AuthRepository, UserRecord
from ..security import (
    REFRESH_COOKIE_NAME,
    AuthenticatedUser,
    create_access_token,
    generate_refresh_token,
    get_current_user,
    hash_refresh_token,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def _serialize_user(user: UserRecord) -> dict[str, object]:
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _set_refresh_cookie(response: Response, raw_refresh: str, config: CoreConfig) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=config.cookie_secure,
        samesite="lax",
        max_age=config.refresh_token_expire_days * 86_400,
        path="/api/v1/auth",
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    """Authenticate credentials and issue short-lived Access JWT + HttpOnly rotating Refresh cookie."""
    config: CoreConfig = request.app.state.config
    auth_repo: AuthRepository = request.app.state.auth_repo
    audit_repo: AuditRepository = request.app.state.audit_repo

    user = await auth_repo.get_user_by_email(body.email.strip())
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    raw_refresh, refresh_hash = generate_refresh_token()
    await auth_repo.issue_refresh_token(
        user_id=user.user_id,
        token_hash=refresh_hash,
        inactivity_days=config.refresh_inactivity_days,
        absolute_days=config.refresh_token_expire_days,
    )
    _set_refresh_cookie(response, raw_refresh, config)

    identity = AuthenticatedUser(user_id=user.user_id, email=user.email, role=user.role)
    access_token = create_access_token(
        identity,
        jwt_secret=config.jwt_secret,
        expire_minutes=config.access_token_expire_minutes,
    )

    await audit_repo.append_log(
        actor_user_id=user.user_id,
        action="USER_LOGIN",
        target_type="user",
        target_id=str(user.user_id),
        details={"email": user.email, "role": user.role},
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in_seconds": config.access_token_expire_minutes * 60,
        "user": _serialize_user(user),
    }


@router.post("/refresh")
async def refresh_session(request: Request, response: Response) -> dict[str, object]:
    """Silently rotate HttpOnly refresh token and issue a fresh short-lived Access Token."""
    config: CoreConfig = request.app.state.config
    auth_repo: AuthRepository = request.app.state.auth_repo

    raw_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token cookie",
        )

    old_hash = hash_refresh_token(raw_cookie)
    new_raw, new_hash = generate_refresh_token()
    rotated = await auth_repo.rotate_refresh_token(
        old_token_hash=old_hash,
        new_token_hash=new_hash,
        inactivity_days=config.refresh_inactivity_days,
    )
    if rotated is None:
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid, expired, or revoked",
        )

    user, _record = rotated
    _set_refresh_cookie(response, new_raw, config)
    identity = AuthenticatedUser(user_id=user.user_id, email=user.email, role=user.role)
    access_token = create_access_token(
        identity,
        jwt_secret=config.jwt_secret,
        expire_minutes=config.access_token_expire_minutes,
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in_seconds": config.access_token_expire_minutes * 60,
        "user": _serialize_user(user),
    }


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    """Revoke active refresh token session and clear HttpOnly cookie."""
    auth_repo: AuthRepository = request.app.state.auth_repo
    raw_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_cookie:
        await auth_repo.revoke_token_by_hash(hash_refresh_token(raw_cookie), reason="USER_LOGOUT")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
    return {"status": "logged_out"}


@router.post("/revoke/{user_id}")
async def revoke_user_sessions(
    user_id: UUID,
    request: Request,
    admin: AuthenticatedUser = Depends(require_roles("ADMIN")),
) -> dict[str, object]:
    """Administrative revocation of all active refresh sessions for a target user."""
    auth_repo: AuthRepository = request.app.state.auth_repo
    audit_repo: AuditRepository = request.app.state.audit_repo
    revoked_count = await auth_repo.revoke_all_user_tokens(user_id, reason="ADMIN_REVOCATION")
    await audit_repo.append_log(
        actor_user_id=admin.user_id,
        action="ADMIN_SESSION_REVOKED",
        target_type="user",
        target_id=str(user_id),
        details={"revoked_tokens": revoked_count},
    )
    return {"user_id": str(user_id), "revoked_tokens": revoked_count}


@router.get("/me")
async def get_me(
    request: Request,
    current: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    """Return authenticated operator/admin/auditor profile."""
    auth_repo: AuthRepository = request.app.state.auth_repo
    user = await auth_repo.get_user_by_id(current.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")
    return _serialize_user(user)
