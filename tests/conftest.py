"""Shared test fixtures."""

from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def _clean_env(monkeypatch):
    """Ensure Cloudreve env vars are unset."""
    monkeypatch.delenv("CLOUDREVE_SERVER", raising=False)
    monkeypatch.delenv("CLOUDREVE_TOKEN", raising=False)


@pytest.fixture
def _mock_config_dir(monkeypatch, tmp_path):
    """Redirect config dir/file to a temp directory for tests."""
    import cloudreve_cli.config as config_mod

    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")
