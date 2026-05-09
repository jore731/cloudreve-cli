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

    # 3. TOML config file with named profiles (stub — full implementation in auth slice #3)
    if CONFIG_FILE.exists():
        import tomllib

        with CONFIG_FILE.open("rb") as f:
            data = tomllib.load(f)

        name = profile_name or data.get("default_profile", "default")
        profiles = data.get("profiles", {})
        prof = profiles.get(name, {})
        if prof:
            return ResolvedConfig(
                server=prof.get("server"),
                token=prof.get("token"),
                source="profile",
                profile=name,
            )

    return ResolvedConfig()
