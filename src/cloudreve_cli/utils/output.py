"""Output formatting utilities.

Supports --output table|json and --quiet mode.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

# Rich console that writes to stderr (keeps stdout clean for piping/JSON)
err_console = Console(stderr=True)


def render_json(data: Any) -> None:
    """Emit raw JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def render_table(
    rows: list[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Render a Rich table to stderr."""
    if not rows:
        err_console.print("[dim]No results.[/dim]")
        return

    cols = columns or list(rows[0].keys())
    table = Table(title=title, show_lines=False)
    for col in cols:
        table.add_column(col)

    for row in rows:
        table.add_row(*(str(row.get(c, "")) for c in cols))

    err_console.print(table)


def render_kv(data: dict[str, Any], *, title: str | None = None) -> None:
    """Render key-value pairs as a two-column Rich table."""
    table = Table(title=title, show_header=False, show_lines=False)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for k, v in data.items():
        table.add_row(str(k), str(v))

    err_console.print(table)


def echo(message: str, *, quiet: bool = False) -> None:
    """Print a message to stderr unless --quiet is active."""
    if not quiet:
        import click

        click.echo(message, err=True)
