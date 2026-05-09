"""Configuration and auth resolution.

Resolution order:
1. CLI flags (--server, --token) — highest priority
2. Environment variables (CLOUDREVE_SERVER, CLOUDREVE_TOKEN) — if ANY env var is set,
   the config file is completely ignored
3. TOML config file (~/.config/cloudreve-cli/config.toml) with named profiles
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CLOUDREVE_CONFIG_DIR", "~/.config/cloudreve-cli")).expanduser()
CONFIG_FILE = CONFIG_DIR / "config.toml"

ENV_SERVER = "CLOUDREVE_SERVER"
ENV_TOKEN = "CLOUDREVE_TOKEN"


@dataclass(frozen=True)
class ResolvedConfig:
    """Resolved configuration for a single CLI invocation."""

    server: str | None = None
    token: str | None = None
    refresh_token: str | None = None
    source: str = "none"  # "cli", "env", "profile", "none"
    profile: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def resolve_config(
    *,
    cli_server: str | None = None,
    cli_token: str | None = None,
    profile_name: str | None = None,
) -> ResolvedConfig:
    """Resolve configuration from CLI flags → env vars → config file."""
    # 1. CLI flags take absolute precedence
    if cli_server or cli_token:
        return ResolvedConfig(
            server=cli_server,
            token=cli_token,
            source="cli",
        )

    # 2. If ANY env var is set, config file is completely ignored
    env_server = os.environ.get(ENV_SERVER)
    env_token = os.environ.get(ENV_TOKEN)
    if env_server or env_token:
        return ResolvedConfig(
            server=env_server,
            token=env_token,
            source="env",
        )

    # 3. TOML config file with named profiles
    if CONFIG_FILE.exists():
        import tomllib

        try:
            with CONFIG_FILE.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            return ResolvedConfig()

        name = profile_name or data.get("default_profile", "default")
        profiles = data.get("profiles", {})
        prof = profiles.get(name, {})
        if prof:
            return ResolvedConfig(
                server=prof.get("server"),
                token=prof.get("access_token"),
                refresh_token=prof.get("refresh_token"),
                source="profile",
                profile=name,
            )

    return ResolvedConfig()


def save_profile(
    name: str,
    *,
    server: str,
    access_token: str,
    refresh_token: str,
) -> None:
    """Save a profile to the TOML config file."""
    import tomli_w

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if CONFIG_FILE.exists():
        import tomllib

        with CONFIG_FILE.open("rb") as f:
            data = tomllib.load(f)

    profiles = data.setdefault("profiles", {})
    profiles[name] = {
        "server": server,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

    # Set default_profile on first login only
    if "default_profile" not in data:
        data["default_profile"] = name

    with CONFIG_FILE.open("wb") as f:
        tomli_w.dump(data, f)


def delete_profile(name: str) -> bool:
    """Remove a profile from the TOML config file. Returns True if found."""
    if not CONFIG_FILE.exists():
        return False

    import tomllib

    import tomli_w

    with CONFIG_FILE.open("rb") as f:
        data = tomllib.load(f)

    profiles = data.get("profiles", {})
    if name not in profiles:
        return False

    del profiles[name]

    # If we deleted the default profile, pick the next one (or clear)
    if data.get("default_profile") == name:
        if profiles:
            data["default_profile"] = next(iter(profiles))
        else:
            data.pop("default_profile", None)

    with CONFIG_FILE.open("wb") as f:
        tomli_w.dump(data, f)

    return True


def list_profiles() -> list[str]:
    """List all profile names from the config file."""
    if not CONFIG_FILE.exists():
        return []

    import tomllib

    try:
        with CONFIG_FILE.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return []

    return list(data.get("profiles", {}).keys())
