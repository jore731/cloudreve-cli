"""Cloudreve file URI parser and builder.

Cloudreve uses ``cloudreve://`` URIs to locate files.  The URI structure is::

    cloudreve://[user@]host/path[?query]

Where:
- **host** (file-system type): ``my``, ``trash``, ``shared_with_me``
- **user** (optional): user ID for admin cross-user access, or share ID
- **path**: file path within the file system
- **query**: optional search conditions (name, category, type, size_gte, …)

This module exposes helpers to:
- *parse* user-friendly path strings into proper URIs
- *build* URIs programmatically
"""

from __future__ import annotations

from urllib.parse import quote, urlencode, urlparse

VALID_HOSTS = frozenset({"my", "trash", "shared_with_me"})
DEFAULT_HOST = "my"


class CloudreveURI:
    """Parsed Cloudreve URI."""

    __slots__ = ("host", "path", "query", "user")

    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        user: str | None = None,
        path: str = "/",
        query: dict[str, str] | None = None,
    ):
        self.host = host
        self.user = user
        self.path = path if path.startswith("/") else f"/{path}"
        self.query = query or {}

    def to_uri(self) -> str:
        """Serialize to a ``cloudreve://`` URI string."""
        user_part = f"{quote(self.user, safe='')}@" if self.user else ""
        encoded_path = quote(self.path, safe="/")
        qs = f"?{urlencode(self.query)}" if self.query else ""
        return f"cloudreve://{user_part}{self.host}{encoded_path}{qs}"

    def __repr__(self) -> str:
        return (
            f"CloudreveURI(host={self.host!r}, user={self.user!r},"
            f" path={self.path!r}, query={self.query!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CloudreveURI):
            return NotImplemented
        return (
            self.host == other.host
            and self.user == other.user
            and self.path == other.path
            and self.query == other.query
        )


def parse_uri(raw: str) -> CloudreveURI:
    """Parse a user-supplied path or ``cloudreve://`` URI.

    Convenience rules:

    - ``/photos``       → ``cloudreve://my/photos``
    - ``photos``        → ``cloudreve://my/photos``
    - ``trash/old``     → ``cloudreve://my/trash/old`` (not trash host!)
    - ``cloudreve://trash/old`` → trash host, path ``/old``
    """
    raw = raw.strip()

    if raw.startswith("cloudreve://"):
        return _parse_full_uri(raw)

    # Treat as a path under the default ``my`` file system.
    path = raw if raw.startswith("/") else f"/{raw}"
    return CloudreveURI(host=DEFAULT_HOST, path=path)


def _parse_full_uri(raw: str) -> CloudreveURI:
    """Parse a fully-qualified ``cloudreve://`` URI."""
    parsed = urlparse(raw)

    host = parsed.hostname or DEFAULT_HOST
    if host not in VALID_HOSTS:
        raise ValueError(
            f"Invalid URI host {host!r}. Must be one of: {', '.join(sorted(VALID_HOSTS))}"
        )

    user = parsed.username or None
    path = parsed.path or "/"

    # Parse query string into a dict
    query: dict[str, str] = {}
    if parsed.query:
        for part in parsed.query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                query[k] = v
            else:
                query[part] = ""

    return CloudreveURI(host=host, user=user, path=path, query=query)


def build_uri(
    path: str = "/",
    *,
    host: str = DEFAULT_HOST,
    user: str | None = None,
    query: dict[str, str] | None = None,
) -> str:
    """Build a ``cloudreve://`` URI string from components."""
    return CloudreveURI(host=host, user=user, path=path, query=query).to_uri()
