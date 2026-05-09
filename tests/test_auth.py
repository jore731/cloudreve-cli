"""Tests for auth commands and auto-refresh middleware."""

from __future__ import annotations

import json

import pytest

from cloudreve_cli.cli import cli
from cloudreve_cli.client import CloudreveClient
from cloudreve_cli.config import save_profile
from cloudreve_cli.exceptions import AuthError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login_response(*, nickname="Test", email="test@example.com"):
    """Build a successful login envelope."""
    return {
        "code": 0,
        "data": {
            "user": {
                "id": "u1",
                "email": email,
                "nickname": nickname,
                "status": "active",
            },
            "token": {
                "access_token": "at_new",
                "refresh_token": "rt_new",
                "access_expires": "2099-01-01T00:00:00Z",
                "refresh_expires": "2099-06-01T00:00:00Z",
            },
        },
    }


def _2fa_required_response(session_id="sess-uuid"):
    return {"code": 203, "data": session_id}


def _refresh_response():
    return {
        "code": 0,
        "data": {
            "access_token": "at_refreshed",
            "refresh_token": "rt_refreshed",
            "access_expires": "2099-01-01T00:00:00Z",
            "refresh_expires": "2099-06-01T00:00:00Z",
        },
    }


def _all_output(result):
    """Combine stdout + stderr for easy assertion."""
    return result.output + (getattr(result, "stderr", None) or "")


# ---------------------------------------------------------------------------
# auth login — basic password flow
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_env", "_mock_config_dir")
class TestAuthLogin:
    def test_login_success_table(self, runner, httpx_mock):
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json=_login_response(),
        )

        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "test@example.com",
                "--password",
                "secret",
            ],
        )
        assert result.exit_code == 0, _all_output(result)
        assert "Logged in as Test" in _all_output(result)

    def test_login_success_json(self, runner, httpx_mock):
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json=_login_response(),
        )

        result = runner.invoke(
            cli,
            [
                "--output",
                "json",
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "test@example.com",
                "--password",
                "secret",
            ],
        )
        assert result.exit_code == 0, _all_output(result)
        data = json.loads(result.output)
        assert data["user"]["email"] == "test@example.com"

    def test_login_saves_profile(self, runner, httpx_mock, tmp_path, monkeypatch):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json=_login_response(),
        )

        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "test@example.com",
                "--password",
                "secret",
                "--profile",
                "myprof",
            ],
        )
        assert result.exit_code == 0, _all_output(result)

        import tomllib

        with (tmp_path / "config.toml").open("rb") as f:
            cfg = tomllib.load(f)
        assert "myprof" in cfg["profiles"]
        assert cfg["profiles"]["myprof"]["access_token"] == "at_new"
        assert cfg["default_profile"] == "myprof"

    def test_login_bad_credentials(self, runner, httpx_mock):
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json={"code": 40001, "msg": "Invalid email or password"},
        )

        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "bad@example.com",
                "--password",
                "wrong",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid email or password" in _all_output(result)


# ---------------------------------------------------------------------------
# auth login — 2FA flow
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_env", "_mock_config_dir")
class TestAuthLogin2FA:
    def test_2fa_with_flag(self, runner, httpx_mock):
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json=_2fa_required_response(),
        )
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token/2fa",
            json=_login_response(),
        )

        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "test@example.com",
                "--password",
                "secret",
                "--2fa-code",
                "123456",
            ],
        )
        assert result.exit_code == 0, _all_output(result)
        assert "Logged in as Test" in _all_output(result)

        # Verify the 2FA request used the correct key "otp" (not "opt")
        twofa_request = httpx_mock.get_requests()[-1]
        body = json.loads(twofa_request.content)
        assert body["otp"] == "123456"
        assert "opt" not in body

    def test_2fa_noninteractive_exit_code_2(self, runner, httpx_mock, monkeypatch):
        """Exit code 2 when 2FA required in non-interactive mode without --2fa-code."""
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json=_2fa_required_response(),
        )

        # Simulate non-interactive: click.prompt raises Abort on EOF
        monkeypatch.setattr("click.prompt", lambda *a, **kw: (_ for _ in ()).throw(EOFError()))

        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "test@example.com",
                "--password",
                "secret",
            ],
        )
        assert result.exit_code == 2
        assert "2FA code required" in _all_output(result)

    def test_2fa_interactive_prompt(self, runner, httpx_mock):
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token",
            json=_2fa_required_response(),
        )
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/session/token/2fa",
            json=_login_response(),
        )

        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--server",
                "https://cloud.example.com",
                "--email",
                "test@example.com",
                "--password",
                "secret",
            ],
            input="654321\n",
        )
        assert result.exit_code == 0, _all_output(result)
        assert "Logged in as Test" in _all_output(result)


# ---------------------------------------------------------------------------
# auth prepare
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_env")
class TestAuthPrepare:
    def test_prepare_table(self, runner, httpx_mock):
        httpx_mock.add_response(
            json={
                "code": 0,
                "data": {
                    "webauthn_enabled": False,
                    "sso_enabled": True,
                    "password_enabled": True,
                    "qq_enabled": False,
                },
            }
        )

        result = runner.invoke(
            cli,
            [
                "--server",
                "https://cloud.example.com",
                "auth",
                "prepare",
                "--email",
                "test@example.com",
            ],
        )
        assert result.exit_code == 0, _all_output(result)
        assert "Password" in _all_output(result)

    def test_prepare_json(self, runner, httpx_mock):
        resp_data = {
            "webauthn_enabled": False,
            "sso_enabled": False,
            "password_enabled": True,
            "qq_enabled": False,
        }
        httpx_mock.add_response(json={"code": 0, "data": resp_data})

        result = runner.invoke(
            cli,
            [
                "--server",
                "https://cloud.example.com",
                "--output",
                "json",
                "auth",
                "prepare",
                "--email",
                "test@example.com",
            ],
        )
        assert result.exit_code == 0, _all_output(result)
        data = json.loads(result.output)
        assert data["password_enabled"] is True


# ---------------------------------------------------------------------------
# auth status
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_env", "_mock_config_dir")
class TestAuthStatus:
    def test_status_no_auth(self, runner):
        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code == 0
        assert "none" in _all_output(result)

    def test_status_with_env(self, runner, monkeypatch):
        monkeypatch.setenv("CLOUDREVE_SERVER", "https://s.example.com")
        monkeypatch.setenv(
            "CLOUDREVE_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSIsImV4cCI6OTk5OTk5OTk5OX0.sig"
        )

        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code == 0
        out = _all_output(result)
        assert "env" in out
        assert "https://s.example.com" in out

    def test_status_json(self, runner):
        result = runner.invoke(cli, ["--output", "json", "auth", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Source" in data


# ---------------------------------------------------------------------------
# auth refresh
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_env", "_mock_config_dir")
class TestAuthRefresh:
    def test_refresh_no_token(self, runner):
        result = runner.invoke(
            cli,
            ["--server", "https://cloud.example.com", "auth", "refresh"],
        )
        assert result.exit_code != 0
        assert "refresh token" in _all_output(result).lower()

    def test_refresh_success(self, runner, httpx_mock, tmp_path, monkeypatch):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        save_profile(
            "default",
            server="https://cloud.example.com",
            access_token="at_old",
            refresh_token="rt_old",
        )

        httpx_mock.add_response(json=_refresh_response())

        result = runner.invoke(cli, ["auth", "refresh"])
        assert result.exit_code == 0, _all_output(result)
        assert "refreshed" in _all_output(result).lower()

        import tomllib

        with (tmp_path / "config.toml").open("rb") as f:
            cfg = tomllib.load(f)
        assert cfg["profiles"]["default"]["access_token"] == "at_refreshed"


# ---------------------------------------------------------------------------
# auth logout
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_clean_env", "_mock_config_dir")
class TestAuthLogout:
    def test_logout_removes_profile(self, runner, tmp_path, monkeypatch, httpx_mock):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        save_profile(
            "default",
            server="https://cloud.example.com",
            access_token="at_old",
            refresh_token="rt_old",
        )

        # Mock the server-side DELETE revocation
        httpx_mock.add_response(json={"code": 0, "data": None})

        result = runner.invoke(cli, ["auth", "logout"])
        assert result.exit_code == 0
        assert "Logged out" in _all_output(result)

    def test_logout_nonexistent_profile(self, runner):
        result = runner.invoke(cli, ["auth", "logout", "--profile", "nope"])
        assert result.exit_code == 0
        assert "not found" in _all_output(result)


# ---------------------------------------------------------------------------
# Auto-refresh middleware (unit test on CloudreveClient directly)
# ---------------------------------------------------------------------------


class TestAutoRefresh:
    def test_auto_refresh_on_401(self, httpx_mock):
        """Client retries after refreshing token on 401."""
        # First request → 401
        httpx_mock.add_response(status_code=401, json={"msg": "expired"})
        # Refresh → success
        httpx_mock.add_response(json=_refresh_response())
        # Retry → success
        httpx_mock.add_response(json={"code": 0, "data": {"ok": True}})

        refreshed = {}

        def on_refresh(access, refresh):
            refreshed["access"] = access
            refreshed["refresh"] = refresh

        client = CloudreveClient(
            server="https://cloud.example.com",
            token="at_old",
            refresh_token="rt_old",
            on_token_refresh=on_refresh,
        )
        result = client.get("/api/v4/something")
        assert result == {"ok": True}
        assert refreshed["access"] == "at_refreshed"
        client.close()

    def test_no_refresh_without_token(self, httpx_mock):
        """Client raises immediately on 401 if no refresh token."""
        httpx_mock.add_response(status_code=401, json={"msg": "unauthorized"})

        client = CloudreveClient(
            server="https://cloud.example.com",
            token="at_old",
        )
        with pytest.raises(AuthError):
            client.get("/api/v4/something")
        client.close()


# ---------------------------------------------------------------------------
# Config persistence helpers
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_mock_config_dir")
class TestConfigPersistence:
    def test_save_and_load_profile(self, tmp_path, monkeypatch):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        save_profile("test", server="https://s.example.com", access_token="at", refresh_token="rt")

        from cloudreve_cli.config import resolve_config

        cfg = resolve_config(profile_name="test")
        assert cfg.server == "https://s.example.com"
        assert cfg.token == "at"
        assert cfg.refresh_token == "rt"
        assert cfg.source == "profile"

    def test_env_overrides_profile(self, tmp_path, monkeypatch):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        save_profile(
            "default", server="https://s.example.com", access_token="at", refresh_token="rt"
        )

        monkeypatch.setenv("CLOUDREVE_SERVER", "https://env.example.com")
        monkeypatch.setenv("CLOUDREVE_TOKEN", "env_token")

        from cloudreve_cli.config import resolve_config

        cfg = resolve_config()
        assert cfg.source == "env"
        assert cfg.server == "https://env.example.com"

    def test_delete_profile(self, tmp_path, monkeypatch):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        save_profile("x", server="https://s.example.com", access_token="at", refresh_token="rt")

        from cloudreve_cli.config import delete_profile

        assert delete_profile("x") is True
        assert delete_profile("x") is False

    def test_list_profiles(self, tmp_path, monkeypatch):
        import cloudreve_cli.config as config_mod

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")

        save_profile("a", server="s", access_token="t", refresh_token="r")
        save_profile("b", server="s", access_token="t", refresh_token="r")

        from cloudreve_cli.config import list_profiles

        profiles = list_profiles()
        assert "a" in profiles
        assert "b" in profiles
