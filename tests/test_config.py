"""Tests for config resolution logic."""

from __future__ import annotations

from cloudreve_cli.config import resolve_config


class TestEnvVarResolution:
    """Env vars take absolute precedence over config file."""

    def test_env_server_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("CLOUDREVE_SERVER", "https://env.example.com")
        cfg = resolve_config()
        assert cfg.server == "https://env.example.com"
        assert cfg.source == "env"

    def test_env_token_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("CLOUDREVE_TOKEN", "env-tok-123")
        cfg = resolve_config()
        assert cfg.token == "env-tok-123"
        assert cfg.source == "env"

    def test_env_both(self, monkeypatch):
        monkeypatch.setenv("CLOUDREVE_SERVER", "https://env.example.com")
        monkeypatch.setenv("CLOUDREVE_TOKEN", "env-tok-123")
        cfg = resolve_config()
        assert cfg.server == "https://env.example.com"
        assert cfg.token == "env-tok-123"
        assert cfg.source == "env"


class TestCLIFlagResolution:
    """CLI flags override everything."""

    def test_cli_server_overrides_env(self, monkeypatch, _clean_env):
        monkeypatch.setenv("CLOUDREVE_SERVER", "https://env.example.com")
        cfg = resolve_config(cli_server="https://cli.example.com")
        assert cfg.server == "https://cli.example.com"
        assert cfg.source == "cli"

    def test_cli_token_overrides_env(self, monkeypatch, _clean_env):
        monkeypatch.setenv("CLOUDREVE_TOKEN", "env-tok")
        cfg = resolve_config(cli_token="cli-tok")
        assert cfg.token == "cli-tok"
        assert cfg.source == "cli"


class TestNoConfig:
    """When nothing is configured."""

    def test_empty_returns_none(self, _clean_env):
        cfg = resolve_config()
        assert cfg.server is None
        assert cfg.token is None
        assert cfg.source == "none"
