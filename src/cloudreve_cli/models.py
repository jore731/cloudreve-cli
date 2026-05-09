"""Pydantic models for Cloudreve v4 API responses."""

from __future__ import annotations

from pydantic import BaseModel


class TokenPair(BaseModel):
    """Access and refresh token pair returned by login/refresh endpoints."""

    access_token: str
    refresh_token: str
    access_expires: str
    refresh_expires: str


class UserGroup(BaseModel):
    """User group info."""

    id: str
    name: str
    permission: str | None = None
    direct_link_batch_size: int | None = None
    trash_retention: int | None = None


class PinnedItem(BaseModel):
    """Pinned sidebar item."""

    uri: str


class UserInfo(BaseModel):
    """User profile from login response."""

    id: str
    email: str
    nickname: str
    status: str
    avatar: str | None = None
    created_at: str | None = None
    credit: int | None = None
    group: UserGroup | None = None
    pined: list[PinnedItem] | None = None
    language: str | None = None


class LoginData(BaseModel):
    """Successful login response data."""

    user: UserInfo
    token: TokenPair


class PrepareLoginData(BaseModel):
    """Available login methods for an account."""

    webauthn_enabled: bool = False
    sso_enabled: bool = False
    password_enabled: bool = True
    qq_enabled: bool = False
