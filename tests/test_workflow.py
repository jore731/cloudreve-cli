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


def _invoke(*args: str) -> ...:
    runner = CliRunner()
    return runner.invoke(cli, ["--server", "https://example.com", *args])


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
