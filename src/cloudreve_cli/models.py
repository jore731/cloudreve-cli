"""Pydantic models for Cloudreve v4 API responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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


# ---------------------------------------------------------------------------
# File listing models
# ---------------------------------------------------------------------------


class FileObject(BaseModel):
    """Single file or folder from a listing response."""

    model_config = ConfigDict(extra="ignore")

    type: int  # 0 = file, 1 = folder
    id: str
    name: str
    size: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    path: str | None = None
    metadata: dict[str, str] | None = None
    capability: str | None = None
    owned: bool | None = None
    primary_entity: str | None = None
    permission: str | None = None


class Pagination(BaseModel):
    """Pagination info from listing response."""

    model_config = ConfigDict(extra="ignore")

    page: int = 0
    page_size: int = 50
    is_cursor: bool = False
    next_page_token: str | None = None


class ListingProps(BaseModel):
    """Listing metadata (capabilities, sort options)."""

    model_config = ConfigDict(extra="ignore")

    capability: str | None = None
    max_page_size: int = 2000
    order_by_options: list[str] | None = None
    order_direction_options: list[str] | None = None


class FileListData(BaseModel):
    """Top-level data from ``GET /api/v4/file`` response."""

    model_config = ConfigDict(extra="ignore")

    files: list[FileObject] = []
    parent: FileObject | None = None
    pagination: Pagination | None = None
    props: ListingProps | None = None
