"""Storage commands — policies, capacity, etc."""

from __future__ import annotations

from cloudreve_cli.cli import GlobalState, cli, pass_state
from cloudreve_cli.models import StoragePolicy
from cloudreve_cli.utils.output import echo, render_json, render_table


@cli.group()
def storage() -> None:
    """Storage policy operations."""


@storage.command()
@pass_state
def policies(state: GlobalState) -> None:
    """List available storage policies (Pro feature)."""
    client = state.make_client()
    with client:
        data = client.get("/api/v4/user/setting/policies")

    if data is None:
        echo("No storage policies found.", quiet=state.quiet)
        return

    items = data if isinstance(data, list) else []
    parsed = [StoragePolicy.model_validate(p) for p in items]

    if state.output == "json":
        render_json([p.model_dump(mode="json") for p in parsed])
        return

    if not parsed:
        echo("No storage policies found.", quiet=state.quiet)
        return

    rows = [
        {
            "ID": p.id,
            "Name": p.name,
            "Type": p.type,
            "Max Size": _humanize_max_size(p.max_size),
        }
        for p in parsed
    ]
    render_table(rows, columns=["ID", "Name", "Type", "Max Size"])


def _humanize_max_size(size: int) -> str:
    """Convert max_size in bytes to human-readable string."""
    if size == 0:
        return "unlimited"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if size == int(size) else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
