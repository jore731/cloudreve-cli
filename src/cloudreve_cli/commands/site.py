"""Site commands — server info and health checks."""

from __future__ import annotations

from cloudreve_cli.cli import GlobalState, cli, pass_state
from cloudreve_cli.utils.output import render_json, render_kv


@cli.group()
def site() -> None:
    """Server information and health checks."""


@site.command()
@pass_state
def ping(state: GlobalState) -> None:
    """Check server connectivity and display basic site info."""
    client = state.make_client()
    with client:
        data = client.get("/api/v4/site/ping")

    if state.output == "json":
        render_json(data)
        return

    if isinstance(data, dict):
        render_kv(data, title="Site Ping")
    else:
        render_kv({"status": data}, title="Site Ping")
