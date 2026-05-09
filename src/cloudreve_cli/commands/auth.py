"""Auth commands — login, prepare, status, refresh, logout."""

from __future__ import annotations

import base64
import json as json_mod
import sys

import click

from cloudreve_cli.cli import cli, pass_state
from cloudreve_cli.client import CloudreveClient
from cloudreve_cli.config import delete_profile, list_profiles, save_profile
from cloudreve_cli.exceptions import AuthError, CloudreveError
from cloudreve_cli.models import LoginData, PrepareLoginData
from cloudreve_cli.utils.output import echo, render_json, render_kv


@cli.group()
def auth() -> None:
    """Manage authentication (login, logout, status, etc.)."""


@auth.command()
@click.option("--server", "login_server", default=None, help="Server URL (overrides global).")
@click.option("--email", prompt="Email", help="Account email.")
@click.option("--password", prompt="Password", hide_input=True, help="Account password.")
@click.option("--2fa-code", "twofa_code", default=None, help="2FA code (prompted if required).")
@click.option(
    "--profile",
    "profile_name",
    default="default",
    show_default=True,
    help="Profile name to save credentials under.",
)
@pass_state
def login(
    state,
    login_server: str | None,
    email: str,
    password: str,
    twofa_code: str | None,
    profile_name: str,
) -> None:
    """Sign in with email and password."""
    server = login_server or state.server
    if not server:
        server = click.prompt("Server URL")

    with CloudreveClient(server=server) as client:
        body = client.post(
            "/api/v4/session/token",
            json={"email": email, "password": password},
            raw=True,
        )

    code = body.get("code", -1)

    # 2FA required (envelope code 203)
    if code == 203:
        session_id = body.get("data", "")
        if not twofa_code:
            try:
                twofa_code = click.prompt("2FA code", err=True)
            except (click.Abort, EOFError) as exc:
                raise AuthError("2FA code required but not provided.") from exc

        with CloudreveClient(server=server) as client:
            body = client.post(
                "/api/v4/session/token/2fa",
                json={"opt": twofa_code, "session_id": session_id},
                raw=True,
            )
            code = body.get("code", -1)

    if code != 0:
        msg = body.get("msg") or body.get("error") or f"Login failed (code={code})"
        raise AuthError(str(msg))

    login_data = LoginData.model_validate(body["data"])

    save_profile(
        profile_name,
        server=server,
        access_token=login_data.token.access_token,
        refresh_token=login_data.token.refresh_token,
    )

    if state.output == "json":
        render_json(body["data"])
    else:
        echo(f"✓ Logged in as {login_data.user.nickname} ({login_data.user.email})")
        echo(f"  Profile saved: {profile_name}")


@auth.command()
@click.option("--email", required=True, help="Account email to check.")
@pass_state
def prepare(state, email: str) -> None:
    """Check available login methods for an account."""
    server = state.require_server()
    with CloudreveClient(server=server) as client:
        data = client.get("/api/v4/session/prepare", params={"email": email})

    info = PrepareLoginData.model_validate(data)

    if state.output == "json":
        render_json(data)
    else:
        render_kv(
            {
                "Password": "✓" if info.password_enabled else "✗",
                "WebAuthn": "✓" if info.webauthn_enabled else "✗",
                "SSO": "✓" if info.sso_enabled else "✗",
                "QQ": "✓" if info.qq_enabled else "✗",
            },
            title=f"Login methods for {email}",
        )


@auth.command()
@pass_state
def status(state) -> None:
    """Show current authentication status."""
    info: dict[str, str] = {
        "Source": state.config_source,
    }
    if state.profile:
        info["Profile"] = state.profile
    if state.server:
        info["Server"] = state.server

    if state.token:
        info["Token"] = state.token[:12] + "…"
        # Try to decode JWT payload for expiry info
        claims = _decode_jwt_payload(state.token)
        if claims:
            if "exp" in claims:
                import datetime

                exp = datetime.datetime.fromtimestamp(claims["exp"], tz=datetime.UTC)
                info["Expires"] = exp.isoformat()
            if "sub" in claims:
                info["Subject"] = str(claims["sub"])
    else:
        info["Token"] = "(none)"

    profiles = list_profiles()
    if profiles:
        info["Profiles"] = ", ".join(profiles)

    if state.output == "json":
        render_json(info)
    else:
        render_kv(info, title="Auth status")


@auth.command()
@pass_state
def refresh(state) -> None:
    """Manually refresh the access token."""
    if not state.refresh_token:
        raise AuthError("No refresh token available. Log in first.")

    server = state.require_server()
    with CloudreveClient(server=server) as client:
        body = client.post(
            "/api/v4/session/token/refresh",
            json={"refresh_token": state.refresh_token},
            raw=True,
        )

    code = body.get("code", -1)
    if code != 0:
        msg = body.get("msg") or body.get("error") or "Refresh failed"
        raise AuthError(str(msg))

    data = body["data"]

    # Persist new tokens if we're using a profile
    if state.config_source == "profile" and state.profile and state.server:
        save_profile(
            state.profile,
            server=state.server,
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
        )

    if state.output == "json":
        render_json(data)
    else:
        echo("✓ Token refreshed successfully.")


@auth.command()
@click.option(
    "--profile", "profile_name", default=None, help="Profile to log out from (default: current)."
)
@pass_state
def logout(state, profile_name: str | None) -> None:
    """Sign out and revoke tokens."""
    name = profile_name or state.profile or "default"

    # Try to revoke on server
    if state.refresh_token and state.server:
        try:
            with CloudreveClient(server=state.server, token=state.token) as client:
                client.delete(
                    "/api/v4/session/token",
                    json={"refresh_token": state.refresh_token},
                )
        except CloudreveError:
            print("Warning: could not revoke session on server.", file=sys.stderr)

    deleted = delete_profile(name)
    if deleted:
        echo(f"✓ Logged out from profile '{name}'.")
    else:
        echo(f"Profile '{name}' not found (may already be removed).")


def _decode_jwt_payload(token: str) -> dict | None:
    """Decode the payload segment of a JWT without verification."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        # Add padding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json_mod.loads(decoded)
    except Exception:
        return None
