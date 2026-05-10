"""Workflow commands — task listing and progress monitoring."""

from __future__ import annotations

from typing import Any

import click

from cloudreve_cli.cli import GlobalState, cli, pass_state
from cloudreve_cli.models import ProgressEntry, WorkflowListData, WorkflowTask
from cloudreve_cli.utils.output import echo, render_json, render_table


@cli.group()
def workflow() -> None:
    """Workflow task management."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _format_datetime(dt: str | None) -> str:
    if not dt:
        return ""
    if "T" in dt:
        return dt.replace("T", " ").split("+")[0].split("Z")[0]
    return dt


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "-"
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes}m"


_STATUS_STYLES = {
    "queued": "[yellow]queued[/yellow]",
    "completed": "[green]completed[/green]",
    "error": "[red]error[/red]",
}


def _task_to_row(t: WorkflowTask) -> dict[str, Any]:
    return {
        "ID": t.id,
        "Type": t.type,
        "Status": t.status,
        "Duration": _format_duration(t.duration),
        "Error": t.error or "",
        "Created": _format_datetime(t.created_at),
    }


def _fetch_task_page(
    client: Any,
    *,
    page: int,
    page_size: int,
) -> WorkflowListData:
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    data = client.get("/api/v4/workflow", params=params)
    return WorkflowListData.model_validate(data)


def _fetch_all_tasks(
    client: Any,
    *,
    page_size: int = 50,
) -> list[WorkflowTask]:
    all_tasks: list[WorkflowTask] = []
    page = 0

    while True:
        listing = _fetch_task_page(client, page=page, page_size=page_size)
        all_tasks.extend(listing.tasks)

        if len(listing.tasks) < page_size:
            break
        page += 1

    return all_tasks


# ---------------------------------------------------------------------------
# ls command
# ---------------------------------------------------------------------------


@workflow.command()
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
def ls(state: GlobalState, page_num: int | None, per_page: int) -> None:
    """List workflow tasks."""
    client = state.make_client()
    with client:
        if page_num is not None:
            listing = _fetch_task_page(client, page=page_num, page_size=per_page)
            tasks = listing.tasks
        else:
            tasks = _fetch_all_tasks(client, page_size=per_page)

    if state.output == "json":
        render_json([t.model_dump(mode="json") for t in tasks])
        return

    if not tasks:
        echo("No workflow tasks.", quiet=state.quiet)
        return

    rows = [_task_to_row(t) for t in tasks]
    render_table(rows, columns=["ID", "Type", "Status", "Duration", "Error", "Created"])


# ---------------------------------------------------------------------------
# progress command
# ---------------------------------------------------------------------------


def _progress_bar(current: int, total: int, width: int = 30) -> str:
    """Build a simple ASCII progress bar."""
    if total <= 0:
        return "N/A"
    ratio = min(current / total, 1.0)
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    pct = ratio * 100
    return f"[{bar}] {pct:.1f}%"


def _humanize_bytes(n: int) -> str:
    if n == 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} PB"


def _format_progress_value(key: str, current: int, total: int) -> str:
    """Format current/total with context-aware units."""
    # Byte-based progress keys
    if key in ("upload", "download") or key.startswith("upload_single_"):
        return f"{_humanize_bytes(current)} / {_humanize_bytes(total)}"
    return f"{current} / {total}"


@workflow.command()
@click.argument("task_id")
@pass_state
def progress(state: GlobalState, task_id: str) -> None:
    """Show realtime progress for a workflow task."""
    client = state.make_client()
    with client:
        data = client.get(f"/api/v4/workflow/progress/{task_id}")

    if state.output == "json":
        render_json(data)
        return

    if not data or not isinstance(data, dict):
        echo("No progress data available.", quiet=state.quiet)
        return

    entries = {k: ProgressEntry.model_validate(v) for k, v in data.items()}

    if not entries:
        echo("No progress data available.", quiet=state.quiet)
        return

    rows: list[dict[str, Any]] = []
    for key, entry in entries.items():
        rows.append(
            {
                "Phase": key,
                "Progress": _progress_bar(entry.current, entry.total),
                "Detail": _format_progress_value(key, entry.current, entry.total),
            }
        )

    render_table(rows, columns=["Phase", "Progress", "Detail"], title=f"Task {task_id}")
