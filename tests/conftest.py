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
