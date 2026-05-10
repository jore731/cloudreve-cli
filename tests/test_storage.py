"""Tests for cloudreve_cli.commands.storage — policies command."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from cloudreve_cli.cli import cli


def _all_output(result):
    """Combine stdout + stderr for easy assertion."""
    return result.output + (getattr(result, "stderr", None) or "")


SAMPLE_POLICIES = [
    {"id": "B1Fy", "name": "Default Local", "type": "local", "max_size": 0},
    {"id": "Emta", "name": "S3 Backup", "type": "s3", "max_size": 10737418240},
    {"id": "J7uV", "name": "COS Archive", "type": "cos", "max_size": 5368709120},
]

_ENVELOPE = {"code": 0, "msg": "", "error": None, "correlation_id": None}


def _policies_response(policies: list[dict]) -> dict:
    return {**_ENVELOPE, "data": policies}


@pytest.fixture
def _storage_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDREVE_SERVER", "https://cloud.example.com")
    monkeypatch.setenv("CLOUDREVE_TOKEN", "test-token")


@pytest.mark.usefixtures("_storage_env")
class TestStoragePolicies:
    def test_policies_json(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/user/setting/policies",
            json=_policies_response(SAMPLE_POLICIES),
        )

        result = runner.invoke(cli, ["--output", "json", "storage", "policies"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["id"] == "B1Fy"
        assert data[1]["type"] == "s3"

    def test_policies_table(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/user/setting/policies",
            json=_policies_response(SAMPLE_POLICIES),
        )

        result = runner.invoke(cli, ["storage", "policies"])
        assert result.exit_code == 0
        combined = _all_output(result)
        assert "B1Fy" in combined
        assert "Default Local" in combined
        assert "S3 Backup" in combined
        assert "unlimited" in combined

    def test_policies_empty(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/user/setting/policies",
            json=_policies_response([]),
        )

        result = runner.invoke(cli, ["storage", "policies"])
        assert result.exit_code == 0
        combined = _all_output(result)
        assert "no storage policies" in combined.lower()

    def test_policies_empty_json(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/user/setting/policies",
            json=_policies_response([]),
        )

        result = runner.invoke(cli, ["--output", "json", "storage", "policies"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_policies_max_size_formatting(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/user/setting/policies",
            json=_policies_response(SAMPLE_POLICIES),
        )

        result = runner.invoke(cli, ["storage", "policies"])
        assert result.exit_code == 0
        combined = _all_output(result)
        # 10737418240 = 10 GB, 5368709120 = 5 GB
        assert "10 GB" in combined
        assert "5 GB" in combined

    def test_policies_extra_fields_ignored(self, httpx_mock, runner: CliRunner) -> None:
        """Extra fields from the API are silently dropped."""
        policies = [
            {
                "id": "X1",
                "name": "Fancy",
                "type": "s3",
                "max_size": 1024,
                "relay": True,
                "weight": 5,
                "chunk_concurrency": 3,
            }
        ]
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/user/setting/policies",
            json=_policies_response(policies),
        )

        result = runner.invoke(cli, ["--output", "json", "storage", "policies"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["id"] == "X1"
