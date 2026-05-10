"""End-to-end tests for `cloudreve site ping`."""

from __future__ import annotations

import json

from click.testing import CliRunner

from cloudreve_cli.cli import cli

PING_RESPONSE = {
    "code": 0,
    "data": {"version": "4.0.0", "site_name": "My Cloud"},
    "msg": "",
    "error": None,
    "correlation_id": None,
}


class TestSitePing:
    """cloudreve site ping — thin E2E tracer."""

    def test_ping_json_output(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=PING_RESPONSE)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--server", "https://example.com", "--output", "json", "site", "ping"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["version"] == "4.0.0"

    def test_ping_table_output(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=PING_RESPONSE)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--server", "https://example.com", "--output", "table", "site", "ping"],
        )
        assert result.exit_code == 0
        # Table output goes to stderr, mixed into result.output by CliRunner
        assert "version" in result.output or "4.0.0" in result.output

    def test_ping_with_env_var(self, httpx_mock, monkeypatch, _clean_env, _mock_config_dir):
        httpx_mock.add_response(json=PING_RESPONSE)
        monkeypatch.setenv("CLOUDREVE_SERVER", "https://env.example.com")
        monkeypatch.setenv("CLOUDREVE_TOKEN", "dummy-tok")
        runner = CliRunner()
        result = runner.invoke(cli, ["--output", "json", "site", "ping"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["version"] == "4.0.0"

    def test_ping_no_server_fails(self, _clean_env, _mock_config_dir):
        runner = CliRunner()
        result = runner.invoke(cli, ["site", "ping"])
        assert result.exit_code != 0

    def test_ping_verbose_logs_to_stderr(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=PING_RESPONSE)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--server",
                "https://example.com",
                "--verbose",
                "--output",
                "json",
                "site",
                "ping",
            ],
        )
        assert result.exit_code == 0
        # Verbose logs go to stderr, mixed into result.output by CliRunner
        assert "GET" in result.output
        assert "200" in result.output

    def test_ping_auth_error(self, httpx_mock, _clean_env):
        httpx_mock.add_response(
            status_code=401,
            json={"msg": "Unauthorized", "code": 401},
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--server", "https://example.com", "--output", "json", "site", "ping"],
        )
        assert result.exit_code == 2

    def test_help_shows_global_options(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--server" in result.output
        assert "--token" in result.output
        assert "--output" in result.output
        assert "--quiet" in result.output
        assert "--verbose" in result.output
        assert "--retries" in result.output
        assert "--profile" in result.output
