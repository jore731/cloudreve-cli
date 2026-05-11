"""Workflow commands — task listing, progress monitoring, and management."""

from __future__ import annotations

import time
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


# ---------------------------------------------------------------------------
# shared helpers for task creation commands
# ---------------------------------------------------------------------------


def _render_task(state: GlobalState, task: dict[str, Any], *, label: str = "Task") -> None:
    """Render a single task response in json or table mode."""
    if state.output == "json":
        render_json(task)
        return

    parsed = WorkflowTask.model_validate(task)
    rows = [_task_to_row(parsed)]
    render_table(rows, columns=["ID", "Type", "Status", "Duration", "Error", "Created"])
    echo(f"{label} created: {parsed.id}", quiet=state.quiet)


def _wait_for_task(
    client: Any,
    task_id: str,
    *,
    state: GlobalState,
    interval: float = 2.0,
    max_wait: float = 3600.0,
) -> None:
    """Poll task progress until it completes or errors out."""
    echo(f"Waiting for task {task_id} ...", quiet=state.quiet)
    start = time.monotonic()

    while time.monotonic() - start < max_wait:
        time.sleep(interval)
        tasks = _fetch_all_tasks(client, page_size=50)
        task = next((t for t in tasks if t.id == task_id), None)
        if task is None:
            echo(f"Task {task_id} not found.", quiet=state.quiet)
            return
        if task.status in ("completed", "error"):
            if task.status == "error":
                echo(f"Task {task_id} failed: {task.error}", quiet=state.quiet)
            else:
                echo(f"Task {task_id} completed.", quiet=state.quiet)
            return
        # Still running — show brief status
        echo(f"  status={task.status}", quiet=state.quiet)

    echo(f"Timed out waiting for task {task_id}.", quiet=state.quiet)


# ---------------------------------------------------------------------------
# relocate command
# ---------------------------------------------------------------------------


@workflow.command()
@click.argument("files", nargs=-1, required=False)
@click.option("--policy", required=True, help="Destination storage policy ID.")
@click.option("--wait", "wait_flag", is_flag=True, help="Poll until task completes.")
@click.option(
    "--stdin",
    "stdin_flag",
    is_flag=True,
    help="Read file URIs from stdin (one per line), for piping.",
)
@pass_state
def relocate(
    state: GlobalState,
    files: tuple[str, ...],
    policy: str,
    wait_flag: bool,
    stdin_flag: bool,
) -> None:
    """Relocate files to a different storage policy.

    FILES are one or more cloudreve:// URIs (or bare paths like /photos).
    Use --stdin to read URIs from stdin (one per line).
    """
    import sys

    from cloudreve_cli.utils.uri import parse_uri

    all_files: list[str] = list(files)

    if stdin_flag:
        for line in sys.stdin:
            stripped = line.strip()
            if stripped:
                all_files.append(stripped)

    if not all_files:
        raise click.UsageError("No files specified. Provide FILES arguments or use --stdin.")

    src_uris = [parse_uri(f).to_uri() for f in all_files]
    payload: dict[str, Any] = {"src": src_uris, "dst_policy_id": policy}

    client = state.make_client()
    with client:
        # NOTE: the endpoint path has a known typo in the Cloudreve API
        data = client.post("/api/v4/workflow/reloacte", json=payload)
        _render_task(state, data)

        if wait_flag and isinstance(data, dict) and data.get("id"):
            _wait_for_task(client, data["id"], state=state)


# ---------------------------------------------------------------------------
# import command
# ---------------------------------------------------------------------------


@workflow.command(name="import")
@click.option("--server-path", required=True, help="Absolute path on the server filesystem.")
@click.option("--dest", required=True, help="Destination cloudreve:// URI (or bare path).")
@click.option("--user-id", default=None, help="Target user hash ID (default: authenticated user).")
@click.option(
    "--policy-id", default=None, type=int, help="Storage policy ID (default: user policy)."
)
@click.option("--recursive", is_flag=True, help="Import recursively.")
@click.option("--extract-media-meta", is_flag=True, help="Extract media metadata.")
@click.option("--wait", "wait_flag", is_flag=True, help="Poll until task completes.")
@pass_state
def import_cmd(
    state: GlobalState,
    server_path: str,
    dest: str,
    user_id: str | None,
    policy_id: int | None,
    recursive: bool,
    extract_media_meta: bool,
    wait_flag: bool,
) -> None:
    """Import files from the server filesystem (admin-only)."""
    from cloudreve_cli.utils.uri import parse_uri

    dst_uri = parse_uri(dest).to_uri()
    payload: dict[str, Any] = {
        "src": server_path,
        "dst": dst_uri,
        "recursive": recursive,
        "extract_media_meta": extract_media_meta,
    }
    if user_id is not None:
        payload["user_id"] = user_id
    if policy_id is not None:
        payload["policy_id"] = policy_id

    client = state.make_client()
    with client:
        data = client.post("/api/v4/workflow/import", json=payload)
        _render_task(state, data)

        if wait_flag and isinstance(data, dict) and data.get("id"):
            _wait_for_task(client, data["id"], state=state)


# ---------------------------------------------------------------------------
# download subgroup
# ---------------------------------------------------------------------------


@workflow.group()
def download() -> None:
    """Remote download management."""


@download.command()
@click.option(
    "--url",
    "urls",
    multiple=True,
    help="Download URL (repeatable). Mutually exclusive with --src-file.",
)
@click.option(
    "--src-file",
    default=None,
    help="cloudreve:// URI to a file containing URLs (one per line).",
)
@click.option("--dest", required=True, help="Destination cloudreve:// URI (or bare path).")
@click.option("--wait", "wait_flag", is_flag=True, help="Poll until task completes.")
@pass_state
def create(
    state: GlobalState,
    urls: tuple[str, ...],
    src_file: str | None,
    dest: str,
    wait_flag: bool,
) -> None:
    """Create a remote download task."""
    from cloudreve_cli.utils.uri import parse_uri

    if not urls and not src_file:
        raise click.UsageError("Provide at least one --url or --src-file.")
    if urls and src_file:
        raise click.UsageError("--url and --src-file are mutually exclusive.")

    dst_uri = parse_uri(dest).to_uri()
    payload: dict[str, Any] = {"dst": dst_uri}

    if urls:
        payload["src"] = list(urls)
    else:
        payload["src_file"] = parse_uri(src_file).to_uri()  # type: ignore[arg-type]

    client = state.make_client()
    with client:
        data = client.post("/api/v4/workflow/download", json=payload)

        # API returns an array of task objects
        if state.output == "json":
            render_json(data)
        elif isinstance(data, list):
            for task_data in data:
                _render_task(state, task_data)
        else:
            _render_task(state, data)

        if wait_flag and isinstance(data, list):
            for task_data in data:
                if isinstance(task_data, dict) and task_data.get("id"):
                    _wait_for_task(client, task_data["id"], state=state)


@download.command()
@click.argument("task_id")
@click.option(
    "--files",
    required=True,
    help="Comma-separated list of file indices to download (0-based).",
)
@pass_state
def select(state: GlobalState, task_id: str, files: str) -> None:
    """Select specific files from a remote download task."""
    file_indices = [int(idx.strip()) for idx in files.split(",")]
    file_args = [{"index": idx} for idx in file_indices]
    payload: dict[str, Any] = {"files": file_args}

    client = state.make_client()
    with client:
        data = client.patch(f"/api/v4/workflow/download/{task_id}", json=payload)

        if state.output == "json":
            render_json(data)
            return

        echo(f"Files selected for task {task_id}.", quiet=state.quiet)


@download.command()
@click.argument("task_id")
@pass_state
def cancel(state: GlobalState, task_id: str) -> None:
    """Cancel a remote download task."""
    client = state.make_client()
    with client:
        data = client.delete(f"/api/v4/workflow/download/{task_id}")

        if state.output == "json":
            render_json(data)
            return

        echo(f"Task {task_id} cancelled.", quiet=state.quiet)
