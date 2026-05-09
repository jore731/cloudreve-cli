"""File commands — listing, browsing, and file operations."""

from __future__ import annotations

from typing import Any

import click

from cloudreve_cli.cli import GlobalState, cli, pass_state
from cloudreve_cli.models import FileListData, FileObject
from cloudreve_cli.utils.output import echo, err_console, render_json, render_table
from cloudreve_cli.utils.uri import parse_uri


@cli.group()
def files() -> None:
    """File and folder operations."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_TYPE_LABELS = {0: "file", 1: "folder"}


def _humanize_size(size: int) -> str:
    """Convert bytes to human-readable string."""
    if size == 0:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} PB"


def _format_datetime(dt: str | None) -> str:
    if not dt:
        return ""
    # Strip timezone info for compact display
    if "T" in dt:
        return dt.split("T")[0]
    return dt


def _file_to_row(f: FileObject) -> dict[str, Any]:
    """Convert a FileObject to a display row dict."""
    return {
        "Name": f.name,
        "Type": _TYPE_LABELS.get(f.type, str(f.type)),
        "Size": _humanize_size(f.size),
        "Modified": _format_datetime(f.updated_at),
    }


def _sort_files(files: list[FileObject], sort_key: str, reverse: bool) -> list[FileObject]:
    """Sort files by the given key. Folders first, then by key."""

    def _key(f: FileObject) -> tuple[int, Any]:
        # Folders first (type=1 → sort as 0), files second (type=0 → sort as 1)
        type_order = 0 if f.type == 1 else 1
        if sort_key == "name":
            return (type_order, f.name.lower())
        elif sort_key == "size":
            return (type_order, f.size)
        elif sort_key == "date":
            return (type_order, f.updated_at or "")
        return (type_order, f.name.lower())

    return sorted(files, key=_key, reverse=reverse)


def _fetch_page(
    client: Any,
    uri_str: str,
    *,
    page: int,
    page_size: int,
    order_by: str | None,
    order_direction: str | None,
) -> FileListData:
    """Fetch a single page of file listings."""
    params: dict[str, Any] = {
        "uri": uri_str,
        "page": page,
        "page_size": page_size,
    }
    if order_by:
        params["order_by"] = order_by
    if order_direction:
        params["order_direction"] = order_direction

    data = client.get("/api/v4/file", params=params)
    return FileListData.model_validate(data)


def _fetch_all_pages(
    client: Any,
    uri_str: str,
    *,
    page_size: int = 100,
    order_by: str | None,
    order_direction: str | None,
) -> list[FileObject]:
    """Auto-paginate through all pages and collect all files."""
    all_files: list[FileObject] = []
    page = 0

    while True:
        listing = _fetch_page(
            client,
            uri_str,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_direction=order_direction,
        )
        all_files.extend(listing.files)

        # Stop if we got fewer files than page_size (last page)
        if len(listing.files) < page_size:
            break

        page += 1

    return all_files


def _ls_recursive(
    client: Any,
    uri_str: str,
    *,
    page_size: int = 100,
    order_by: str | None,
    order_direction: str | None,
    depth: int = 0,
    max_depth: int = 50,
) -> list[tuple[FileObject, int]]:
    """Recursively list files with depth info for indentation."""
    if depth > max_depth:
        return []

    files = _fetch_all_pages(
        client,
        uri_str,
        page_size=page_size,
        order_by=order_by,
        order_direction=order_direction,
    )

    results: list[tuple[FileObject, int]] = []
    for f in files:
        results.append((f, depth))
        if f.type == 1 and f.path:
            # Recurse into subfolders
            results.extend(
                _ls_recursive(
                    client,
                    f.path,
                    page_size=page_size,
                    order_by=order_by,
                    order_direction=order_direction,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )

    return results


# ---------------------------------------------------------------------------
# ls command
# ---------------------------------------------------------------------------


@files.command()
@click.argument("path", default="cloudreve://my/")
@click.option(
    "--short",
    "-s",
    is_flag=True,
    help="Compact output — names only.",
)
@click.option(
    "--recursive",
    "-R",
    is_flag=True,
    help="List files recursively.",
)
@click.option(
    "--sort",
    "sort_key",
    type=click.Choice(["name", "size", "date"], case_sensitive=False),
    default="name",
    show_default=True,
    help="Sort key for output.",
)
@click.option(
    "--reverse",
    is_flag=True,
    help="Reverse sort order.",
)
@click.option(
    "--page",
    "page_num",
    type=int,
    default=None,
    help="Specific page number (0-based). Disables auto-pagination.",
)
@click.option(
    "--per-page",
    type=int,
    default=50,
    show_default=True,
    help="Items per page.",
)
@pass_state
def ls(
    state: GlobalState,
    path: str,
    short: bool,
    recursive: bool,
    sort_key: str,
    reverse: bool,
    page_num: int | None,
    per_page: int,
) -> None:
    """List files and folders.

    PATH is a Cloudreve URI or a shorthand path (e.g. /photos → cloudreve://my/photos).
    """
    parsed = parse_uri(path)
    uri_str = parsed.to_uri()

    # Map CLI sort keys to API order_by values
    api_order_map = {"name": "name", "size": "size", "date": "updated_at"}
    api_order_by = api_order_map.get(sort_key)
    api_direction = "desc" if reverse else "asc"

    client = state.make_client()
    with client:
        if recursive:
            file_depth_pairs = _ls_recursive(
                client,
                uri_str,
                page_size=per_page,
                order_by=api_order_by,
                order_direction=api_direction,
            )
            _render_recursive(state, file_depth_pairs, short=short)
            return

        if page_num is not None:
            # Single page mode
            listing = _fetch_page(
                client,
                uri_str,
                page=page_num,
                page_size=per_page,
                order_by=api_order_by,
                order_direction=api_direction,
            )
            files = listing.files
        else:
            # Auto-pagination
            files = _fetch_all_pages(
                client,
                uri_str,
                page_size=per_page,
                order_by=api_order_by,
                order_direction=api_direction,
            )

        # Client-side sort (on top of server sort)
        files = _sort_files(files, sort_key, reverse)

        _render_files(state, files, short=short)


def _render_files(state: GlobalState, files: list[FileObject], *, short: bool) -> None:
    """Render a flat file list."""
    if state.output == "json":
        render_json([f.model_dump(mode="json") for f in files])
        return

    if not files:
        echo("No files found.", quiet=state.quiet)
        return

    if short:
        for f in files:
            prefix = "📁 " if f.type == 1 else "   "
            click.echo(f"{prefix}{f.name}")
        return

    rows = [_file_to_row(f) for f in files]
    render_table(rows, columns=["Name", "Type", "Size", "Modified"])


def _render_recursive(
    state: GlobalState,
    file_depth_pairs: list[tuple[FileObject, int]],
    *,
    short: bool,
) -> None:
    """Render a recursive file listing with indentation."""
    if state.output == "json":
        render_json([{**f.model_dump(mode="json"), "_depth": d} for f, d in file_depth_pairs])
        return

    if not file_depth_pairs:
        echo("No files found.", quiet=state.quiet)
        return

    if short:
        for f, depth in file_depth_pairs:
            indent = "  " * depth
            prefix = "📁 " if f.type == 1 else "   "
            click.echo(f"{indent}{prefix}{f.name}")
        return

    # Tree-style output using Rich
    from rich.tree import Tree

    root = Tree("📂 .")
    # Map depth → parent tree node
    depth_nodes: dict[int, Any] = {-1: root}

    for f, depth in file_depth_pairs:
        icon = "📁" if f.type == 1 else "📄"
        size_str = _humanize_size(f.size) if f.type == 0 else ""
        date_str = _format_datetime(f.updated_at)
        label = f"{icon} {f.name}"
        if size_str:
            label += f"  [dim]({size_str})[/dim]"
        if date_str:
            label += f"  [dim]{date_str}[/dim]"

        parent = depth_nodes.get(depth - 1, root)
        node = parent.add(label)
        depth_nodes[depth] = node

    err_console.print(root)
