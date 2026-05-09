"""Root CLI group with global options."""

from __future__ import annotations

import sys

import click

from cloudreve_cli import exit_codes
from cloudreve_cli.client import CloudreveClient
from cloudreve_cli.config import resolve_config
from cloudreve_cli.exceptions import CloudreveError


class CloudreveGroup(click.Group):
    """Click group that maps CloudreveError to proper exit codes."""

    def invoke(self, ctx: click.Context) -> None:
        try:
            return super().invoke(ctx)
        except CloudreveError as exc:
            click.echo(f"Error: {exc}", err=True)
            raise SystemExit(exc.exit_code) from exc


class GlobalState:
    """Bag of resolved global options, attached to Click context."""

    def __init__(
        self,
        *,
        output: str,
        quiet: bool,
        verbose: bool,
        retries: int,
        server: str | None,
        token: str | None,
        profile: str | None,
    ):
        self.output = output
        self.quiet = quiet
        self.verbose = verbose
        self.retries = retries

        cfg = resolve_config(
            cli_server=server,
            cli_token=token,
            profile_name=profile,
        )
        self.server = cfg.server
        self.token = cfg.token
        self.refresh_token = cfg.refresh_token
        self.config_source = cfg.source
        self.profile = cfg.profile

    def require_server(self) -> str:
        """Return server URL or exit with auth error."""
        if not self.server:
            raise CloudreveError(
                "No server configured. Use --server, CLOUDREVE_SERVER env var, "
                "or set up a profile with `cloudreve auth login`.",
                exit_code=exit_codes.AUTH_ERROR,
            )
        return self.server

    def _handle_token_refresh(self, new_access: str, new_refresh: str) -> None:
        """Persist refreshed tokens back to config profile."""
        if self.config_source == "profile" and self.profile:
            from cloudreve_cli.config import save_profile

            save_profile(
                self.profile,
                server=self.server or "",
                access_token=new_access,
                refresh_token=new_refresh,
            )

    def make_client(self) -> CloudreveClient:
        """Build a CloudreveClient from resolved config."""
        return CloudreveClient(
            server=self.require_server(),
            token=self.token,
            refresh_token=self.refresh_token,
            retries=self.retries,
            verbose=self.verbose,
            on_token_refresh=self._handle_token_refresh,
        )


pass_state = click.make_pass_decorator(GlobalState)


@click.group(cls=CloudreveGroup)
@click.option("--server", default=None, help="Cloudreve server URL.")
@click.option("--token", default=None, help="Bearer token for auth.")
@click.option("--profile", "-p", default=None, help="Named config profile to use.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format.",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output.")
@click.option("--verbose", "-v", is_flag=True, help="Log HTTP details to stderr.")
@click.option(
    "--retries",
    type=int,
    default=0,
    show_default=True,
    help="Number of retries on 5xx/connection errors (exponential backoff).",
)
@click.version_option(package_name="cloudreve-cli")
@click.pass_context
def cli(
    ctx: click.Context,
    server: str | None,
    token: str | None,
    profile: str | None,
    output: str,
    quiet: bool,
    verbose: bool,
    retries: int,
) -> None:
    """cloudreve-cli — Full-coverage CLI for the Cloudreve v4 API."""
    ctx.ensure_object(dict)
    ctx.obj = GlobalState(
        output=output,
        quiet=quiet,
        verbose=verbose,
        retries=retries,
        server=server,
        token=token,
        profile=profile,
    )


def main() -> None:
    """Entry point that catches CloudreveError and sets exit codes."""
    try:
        cli(standalone_mode=False)
    except CloudreveError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(exc.exit_code)
    except click.exceptions.Exit as exc:
        sys.exit(exc.exit_code)
    except click.Abort:
        sys.exit(exit_codes.GENERAL_ERROR)


# Register command groups
from cloudreve_cli.commands import auth as _auth  # noqa: E402, F401
from cloudreve_cli.commands import files as _files  # noqa: E402, F401
from cloudreve_cli.commands import site as _site  # noqa: E402, F401
