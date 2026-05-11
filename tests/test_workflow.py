"""End-to-end tests for ``cloudreve workflow`` commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

from cloudreve_cli.cli import cli

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_ENVELOPE = {"code": 0, "msg": "", "error": None, "correlation_id": None}

TASK_A = {
    "id": "task-aaa",
    "status": "queued",
    "type": "relocate",
    "summary": {"phase": "uploading", "props": {}},
    "duration": 125,
    "error": None,
    "node": "node-1",
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:32:05Z",
}

TASK_B = {
    "id": "task-bbb",
    "status": "completed",
    "type": "create_archive",
    "summary": None,
    "duration": 3661,
    "error": None,
    "node": "node-2",
    "created_at": "2025-01-14T08:00:00Z",
    "updated_at": "2025-01-14T09:01:01Z",
}

TASK_C = {
    "id": "task-ccc",
    "status": "error",
    "type": "extract_archive",
    "summary": None,
    "duration": 0,
    "error": "zip: corrupted",
    "node": None,
    "created_at": "2025-01-13T12:00:00Z",
    "updated_at": "2025-01-13T12:00:00Z",
}


def _workflow_list_response(tasks: list[dict], page: int = 0, page_size: int = 50) -> dict:
    return {
        **_ENVELOPE,
        "data": {
            "tasks": tasks,
            "pagination": {"page": page, "page_size": page_size, "is_cursor": True},
        },
    }


PROGRESS_DATA = {
    "upload_count": {"total": 34, "current": 25},
    "upload": {"total": 12_836_332, "current": 16_889},
}


def _progress_response(data: dict) -> dict:
    return {**_ENVELOPE, "data": data}


def _invoke(*args: str, input: str | None = None) -> ...:
    runner = CliRunner()
    return runner.invoke(cli, ["--server", "https://example.com", *args], input=input)


# ---------------------------------------------------------------------------
# workflow ls
# ---------------------------------------------------------------------------


class TestWorkflowLs:
    def test_ls_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(
            json=_workflow_list_response([TASK_A, TASK_B]),
        )
        result = _invoke("--output", "json", "workflow", "ls")
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "task-aaa"
        assert parsed[1]["status"] == "completed"

    def test_ls_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(
            json=_workflow_list_response([TASK_A, TASK_B, TASK_C]),
        )
        result = _invoke("--output", "table", "workflow", "ls")
        assert result.exit_code == 0
        assert "task-aaa" in result.output
        assert "relocate" in result.output
        assert "corrupted" in result.output

    def test_ls_empty(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_workflow_list_response([]))
        result = _invoke("--output", "table", "workflow", "ls")
        assert result.exit_code == 0
        assert "No workflow tasks" in result.output

    def test_ls_empty_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_workflow_list_response([]))
        result = _invoke("--output", "json", "workflow", "ls")
        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_ls_pagination(self, httpx_mock, _clean_env):
        """Auto-pagination fetches all pages."""
        page0_tasks = [TASK_A, TASK_B]
        page1_tasks = [TASK_C]
        httpx_mock.add_response(
            json=_workflow_list_response(page0_tasks, page=0, page_size=2),
        )
        httpx_mock.add_response(
            json=_workflow_list_response(page1_tasks, page=1, page_size=2),
        )
        result = _invoke("--output", "json", "workflow", "ls", "--per-page", "2")
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 3

    def test_ls_specific_page(self, httpx_mock, _clean_env):
        httpx_mock.add_response(
            json=_workflow_list_response([TASK_B], page=1, page_size=50),
        )
        result = _invoke("--output", "json", "workflow", "ls", "--page", "1")
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1
        assert parsed[0]["id"] == "task-bbb"

    def test_ls_duration_formatting(self, httpx_mock, _clean_env):
        httpx_mock.add_response(
            json=_workflow_list_response([TASK_A, TASK_B]),
        )
        result = _invoke("--output", "table", "workflow", "ls")
        assert result.exit_code == 0
        assert "2m5s" in result.output  # 125s
        assert "1h1m" in result.output  # 3661s


# ---------------------------------------------------------------------------
# workflow progress
# ---------------------------------------------------------------------------


class TestWorkflowProgress:
    def test_progress_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_progress_response(PROGRESS_DATA))
        result = _invoke("--output", "json", "workflow", "progress", "task-aaa")
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["upload_count"]["total"] == 34
        assert parsed["upload"]["current"] == 16_889

    def test_progress_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_progress_response(PROGRESS_DATA))
        result = _invoke("--output", "table", "workflow", "progress", "task-aaa")
        assert result.exit_code == 0
        assert "upload_count" in result.output
        assert "upload" in result.output
        assert "25 / 34" in result.output

    def test_progress_empty(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_progress_response({}))
        result = _invoke("--output", "table", "workflow", "progress", "task-xyz")
        assert result.exit_code == 0
        assert "No progress data" in result.output

    def test_progress_empty_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_progress_response({}))
        result = _invoke("--output", "json", "workflow", "progress", "task-xyz")
        assert result.exit_code == 0
        # JSON mode returns raw data even if empty
        parsed = json.loads(result.output)
        assert parsed == {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _task_response(task: dict) -> dict:
    """Wrap a single task dict in the standard API envelope."""
    return {**_ENVELOPE, "data": task}


def _task_list_response(tasks: list[dict]) -> dict:
    """Wrap a list of task dicts (download returns arrays)."""
    return {**_ENVELOPE, "data": tasks}


# ---------------------------------------------------------------------------
# workflow relocate
# ---------------------------------------------------------------------------


class TestWorkflowRelocate:
    def test_relocate_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "relocate",
            "cloudreve://my/1/file.pdf",
            "--policy",
            "J7uV",
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == "task-aaa"

    def test_relocate_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "table",
            "workflow",
            "relocate",
            "/photos/a.jpg",
            "--policy",
            "ABCD",
        )
        assert result.exit_code == 0
        assert "task-aaa" in result.output
        assert "created" in result.output.lower()

    def test_relocate_multiple_files(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "relocate",
            "/photos/a.jpg",
            "cloudreve://my/docs/b.pdf",
            "--policy",
            "XYZ",
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert len(body["src"]) == 2
        assert body["dst_policy_id"] == "XYZ"

    def test_relocate_uses_typo_endpoint(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "relocate",
            "/file.txt",
            "--policy",
            "P1",
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "/workflow/reloacte" in str(req.url)

    def test_relocate_missing_policy(self, _clean_env):
        result = _invoke("workflow", "relocate", "/file.txt")
        assert result.exit_code != 0
        assert "policy" in result.output.lower() or "required" in result.output.lower()

    def test_relocate_no_files_error(self, _clean_env):
        result = _invoke("workflow", "relocate", "--policy", "P1")
        assert result.exit_code != 0
        assert "no files" in result.output.lower()


# ---------------------------------------------------------------------------
# workflow relocate --stdin
# ---------------------------------------------------------------------------


class TestWorkflowRelocateStdin:
    def test_relocate_stdin(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        stdin_data = "cloudreve://my/file1.txt\ncloudreve://my/file2.txt\n"
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "relocate",
            "--policy",
            "P1",
            "--stdin",
            input=stdin_data,
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert len(body["src"]) == 2
        assert body["src"][0] == "cloudreve://my/file1.txt"
        assert body["src"][1] == "cloudreve://my/file2.txt"
        assert body["dst_policy_id"] == "P1"

    def test_relocate_stdin_with_args(self, httpx_mock, _clean_env):
        """--stdin combines with positional arguments."""
        httpx_mock.add_response(json=_task_response(TASK_A))
        stdin_data = "cloudreve://my/stdin-file.txt\n"
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "relocate",
            "/arg-file.txt",
            "--policy",
            "P1",
            "--stdin",
            input=stdin_data,
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert len(body["src"]) == 2
        assert body["src"][0] == "cloudreve://my/arg-file.txt"
        assert body["src"][1] == "cloudreve://my/stdin-file.txt"

    def test_relocate_stdin_empty_lines_skipped(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        stdin_data = "\n\ncloudreve://my/file.txt\n\n"
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "relocate",
            "--policy",
            "P1",
            "--stdin",
            input=stdin_data,
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert len(body["src"]) == 1

    def test_relocate_stdin_empty_error(self, _clean_env):
        result = _invoke("workflow", "relocate", "--policy", "P1", "--stdin", input="")
        assert result.exit_code != 0
        assert "no files" in result.output.lower()


# ---------------------------------------------------------------------------
# workflow import
# ---------------------------------------------------------------------------


class TestWorkflowImport:
    def test_import_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "import",
            "--server-path",
            "/data/uploads",
            "--dest",
            "/imported",
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == "task-aaa"
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["src"] == "/data/uploads"
        assert "user_id" not in body
        assert "policy_id" not in body
        assert body["recursive"] is False

    def test_import_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "table",
            "workflow",
            "import",
            "--server-path",
            "/srv",
            "--dest",
            "/dest",
        )
        assert result.exit_code == 0
        assert "task-aaa" in result.output

    def test_import_recursive(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "import",
            "--server-path",
            "/srv",
            "--dest",
            "/dest",
            "--recursive",
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert body["recursive"] is True

    def test_import_extract_media_meta(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "import",
            "--server-path",
            "/srv",
            "--dest",
            "/dest",
            "--extract-media-meta",
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert body["extract_media_meta"] is True

    def test_import_endpoint_path(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_response(TASK_A))
        _invoke(
            "--output",
            "json",
            "workflow",
            "import",
            "--server-path",
            "/srv",
            "--dest",
            "/dest",
        )
        req = httpx_mock.get_request()
        assert "/workflow/import" in str(req.url)

    def test_import_with_user_id_and_policy_id(self, httpx_mock, _clean_env):
        """When explicit --user-id / --policy-id are given, they appear in the payload."""
        httpx_mock.add_response(json=_task_response(TASK_A))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "import",
            "--server-path",
            "/srv",
            "--dest",
            "/dest",
            "--user-id",
            "usr42",
            "--policy-id",
            "7",
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert body["user_id"] == "usr42"
        assert body["policy_id"] == 7


# ---------------------------------------------------------------------------
# --wait polling (_wait_for_task)
# ---------------------------------------------------------------------------


class TestWaitForTask:
    """Test the --wait flag polling logic via ``workflow relocate --wait``."""

    def _relocate_wait(self, httpx_mock, monkeypatch, poll_responses):
        """Helper: invoke relocate --wait with mocked time and poll responses.

        ``poll_responses`` is a list of task-list JSON dicts that will be
        returned on successive polling GETs *after* the initial POST.
        """
        # First response is the POST /workflow/reloacte returning a task
        httpx_mock.add_response(json=_task_response(TASK_A))
        # Subsequent GETs return poll_responses in order
        for resp in poll_responses:
            httpx_mock.add_response(json=resp)

        # Make time.sleep a no-op so tests don't actually wait
        monkeypatch.setattr("cloudreve_cli.commands.workflow.time.sleep", lambda _: None)

        # Make time.monotonic advance by 1 second per call (far below timeout)
        counter = {"n": 0}

        def fake_monotonic():
            counter["n"] += 1
            return float(counter["n"])

        monkeypatch.setattr("cloudreve_cli.commands.workflow.time.monotonic", fake_monotonic)

        return _invoke(
            "workflow",
            "relocate",
            "/file.txt",
            "--policy",
            "P1",
            "--wait",
        )

    def test_wait_completed(self, httpx_mock, _clean_env, monkeypatch):
        completed_task = {**TASK_A, "status": "completed"}
        result = self._relocate_wait(
            httpx_mock, monkeypatch, [_workflow_list_response([completed_task])]
        )
        assert result.exit_code == 0
        assert "completed" in result.output.lower()

    def test_wait_error(self, httpx_mock, _clean_env, monkeypatch):
        error_task = {**TASK_A, "status": "error", "error": "disk full"}
        result = self._relocate_wait(
            httpx_mock, monkeypatch, [_workflow_list_response([error_task])]
        )
        assert result.exit_code == 0
        assert "failed" in result.output.lower()
        assert "disk full" in result.output.lower()

    def test_wait_not_found(self, httpx_mock, _clean_env, monkeypatch):
        # Polling returns an empty task list — task disappeared
        result = self._relocate_wait(httpx_mock, monkeypatch, [_workflow_list_response([])])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_wait_timeout(self, httpx_mock, _clean_env, monkeypatch):
        """If the task stays queued and monotonic exceeds max_wait, we time out."""
        running_task = {**TASK_A, "status": "queued"}

        # First response: POST creating the task
        httpx_mock.add_response(json=_task_response(TASK_A))
        # One polling GET (task stays queued, then loop exits on timeout)
        httpx_mock.add_response(json=_workflow_list_response([running_task]))

        # Wall-clock mock: sleep() jumps past max_wait so timeout triggers
        # after exactly one poll iteration.  monotonic() returns the clock
        # value; client.request() also calls monotonic() for timing but that
        # just sees the same stable value and doesn't advance the clock.
        _clock = {"t": 0.0}

        def fake_monotonic():
            return _clock["t"]

        def fake_sleep(_seconds):
            _clock["t"] += 4000.0  # jump past 3600s max_wait

        monkeypatch.setattr("cloudreve_cli.commands.workflow.time.sleep", fake_sleep)
        monkeypatch.setattr("cloudreve_cli.commands.workflow.time.monotonic", fake_monotonic)

        result = _invoke(
            "workflow",
            "relocate",
            "/file.txt",
            "--policy",
            "P1",
            "--wait",
        )
        assert result.exit_code == 0
        assert "timed out" in result.output.lower()

    def test_wait_polls_then_completes(self, httpx_mock, _clean_env, monkeypatch):
        """Task is running on first poll, then completes on second poll."""
        running_task = {**TASK_A, "status": "processing"}
        completed_task = {**TASK_A, "status": "completed"}
        result = self._relocate_wait(
            httpx_mock,
            monkeypatch,
            [
                _workflow_list_response([running_task]),
                _workflow_list_response([completed_task]),
            ],
        )
        assert result.exit_code == 0
        assert "completed" in result.output.lower()


# ---------------------------------------------------------------------------
# workflow download create
# ---------------------------------------------------------------------------


class TestWorkflowDownloadCreate:
    def test_create_with_urls_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_list_response([TASK_A]))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "create",
            "--url",
            "https://example.com/file.zip",
            "--dest",
            "/downloads",
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]["id"] == "task-aaa"

    def test_create_with_src_file(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_list_response([TASK_A]))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "create",
            "--src-file",
            "cloudreve://my/urls.txt",
            "--dest",
            "/downloads",
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert "src_file" in body
        assert "src" not in body

    def test_create_multiple_urls(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_list_response([TASK_A, TASK_B]))
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "create",
            "--url",
            "https://example.com/a.zip",
            "--url",
            "https://example.com/b.zip",
            "--dest",
            "/downloads",
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert len(body["src"]) == 2

    def test_create_no_url_or_src_file(self, _clean_env):
        result = _invoke(
            "workflow",
            "download",
            "create",
            "--dest",
            "/downloads",
        )
        assert result.exit_code != 0

    def test_create_url_and_src_file_conflict(self, _clean_env):
        result = _invoke(
            "workflow",
            "download",
            "create",
            "--url",
            "https://example.com/f.zip",
            "--src-file",
            "/urls.txt",
            "--dest",
            "/downloads",
        )
        assert result.exit_code != 0

    def test_create_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json=_task_list_response([TASK_A]))
        result = _invoke(
            "--output",
            "table",
            "workflow",
            "download",
            "create",
            "--url",
            "https://example.com/f.zip",
            "--dest",
            "/downloads",
        )
        assert result.exit_code == 0
        assert "task-aaa" in result.output


# ---------------------------------------------------------------------------
# workflow download select
# ---------------------------------------------------------------------------


class TestWorkflowDownloadSelect:
    def test_select_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json={**_ENVELOPE, "data": None})
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "select",
            "task-aaa",
            "--files",
            "0,2,5",
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert body["files"] == [{"index": 0}, {"index": 2}, {"index": 5}]

    def test_select_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json={**_ENVELOPE, "data": None})
        result = _invoke(
            "--output",
            "table",
            "workflow",
            "download",
            "select",
            "task-aaa",
            "--files",
            "1",
        )
        assert result.exit_code == 0
        assert "selected" in result.output.lower()

    def test_select_endpoint_path(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json={**_ENVELOPE, "data": None})
        _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "select",
            "taskXYZ",
            "--files",
            "0",
        )
        req = httpx_mock.get_request()
        assert "/workflow/download/taskXYZ" in str(req.url)
        assert req.method == "PATCH"


# ---------------------------------------------------------------------------
# workflow download cancel
# ---------------------------------------------------------------------------


class TestWorkflowDownloadCancel:
    def test_cancel_json(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json={**_ENVELOPE, "data": None})
        result = _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "cancel",
            "task-aaa",
        )
        assert result.exit_code == 0

    def test_cancel_table(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json={**_ENVELOPE, "data": None})
        result = _invoke(
            "--output",
            "table",
            "workflow",
            "download",
            "cancel",
            "task-aaa",
        )
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    def test_cancel_endpoint_path(self, httpx_mock, _clean_env):
        httpx_mock.add_response(json={**_ENVELOPE, "data": None})
        _invoke(
            "--output",
            "json",
            "workflow",
            "download",
            "cancel",
            "task-abc",
        )
        req = httpx_mock.get_request()
        assert "/workflow/download/task-abc" in str(req.url)
        assert req.method == "DELETE"
