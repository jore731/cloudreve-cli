"""Tests for cloudreve_cli.commands.files — ls command."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from cloudreve_cli.cli import cli


def _all_output(result):
    """Combine stdout + stderr for easy assertion."""
    return result.output + (getattr(result, "stderr", None) or "")


@pytest.fixture
def _files_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env vars for a valid auth context."""
    monkeypatch.setenv("CLOUDREVE_SERVER", "https://cloud.example.com")
    monkeypatch.setenv("CLOUDREVE_TOKEN", "test-token")


def _listing_response(
    files: list[dict] | None = None,
    parent: dict | None = None,
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """Build a standard listing API response envelope."""
    if files is None:
        files = []
    return {
        "code": 0,
        "data": {
            "files": files,
            "parent": parent
            or {
                "type": 1,
                "id": "root",
                "name": "",
                "size": 0,
                "path": "cloudreve://my/",
            },
            "pagination": {"page": page, "page_size": page_size, "is_cursor": False},
            "props": {
                "capability": "39/9",
                "max_page_size": 2000,
                "order_by_options": ["name", "size", "updated_at", "created_at"],
                "order_direction_options": ["asc", "desc"],
            },
        },
        "msg": "",
    }


SAMPLE_FILES = [
    {
        "type": 1,
        "id": "folder1",
        "name": "Documents",
        "size": 0,
        "created_at": "2025-01-10T10:00:00+00:00",
        "updated_at": "2025-01-15T12:00:00+00:00",
        "path": "cloudreve://my/Documents",
    },
    {
        "type": 0,
        "id": "file1",
        "name": "photo.jpg",
        "size": 2048000,
        "created_at": "2025-02-01T08:00:00+00:00",
        "updated_at": "2025-02-02T09:30:00+00:00",
        "path": "cloudreve://my/photo.jpg",
    },
    {
        "type": 0,
        "id": "file2",
        "name": "notes.txt",
        "size": 512,
        "created_at": "2025-01-20T14:00:00+00:00",
        "updated_at": "2025-01-20T14:30:00+00:00",
        "path": "cloudreve://my/notes.txt",
    },
]


# ---------------------------------------------------------------------------
# Basic listing
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_files_env")
class TestFilesLs:
    def test_ls_table_output(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls"])
        assert result.exit_code == 0
        combined = _all_output(result)
        assert "Documents" in combined
        assert "photo.jpg" in combined
        assert "notes.txt" in combined

    def test_ls_json_output(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["--output", "json", "files", "ls"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3

    def test_ls_short_mode(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "--short"])
        assert result.exit_code == 0
        assert "📁 Documents" in result.output
        assert "photo.jpg" in result.output

    def test_ls_empty_dir(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response([]),
        )

        result = runner.invoke(cli, ["files", "ls"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Custom path
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_files_env")
class TestFilesLsPath:
    def test_shorthand_path(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2Fphotos&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "/photos"])
        assert result.exit_code == 0

    def test_full_uri(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Ftrash%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "cloudreve://trash/"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_files_env")
class TestFilesLsSort:
    def test_sort_by_size(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=size&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "--sort", "size"])
        assert result.exit_code == 0

    def test_reverse_sort(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=desc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "--reverse"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_files_env")
class TestFilesLsPagination:
    def test_specific_page(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=2&page_size=10&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES, page=2, page_size=10),
        )

        result = runner.invoke(cli, ["files", "ls", "--page", "2", "--per-page", "10"])
        assert result.exit_code == 0

    def test_auto_pagination(self, httpx_mock, runner: CliRunner) -> None:
        """Auto-pagination fetches multiple pages until fewer items than page_size."""
        page0_files = [
            {"type": 0, "id": f"f{i}", "name": f"file{i}.txt", "size": 100} for i in range(3)
        ]
        page1_files = [
            {"type": 0, "id": "f3", "name": "file3.txt", "size": 100},
        ]

        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=3&order_by=name&order_direction=asc",
            json=_listing_response(page0_files, page_size=3),
        )
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=1&page_size=3&order_by=name&order_direction=asc",
            json=_listing_response(page1_files, page_size=3),
        )

        result = runner.invoke(cli, ["files", "ls", "--per-page", "3"])
        assert result.exit_code == 0
        # All 4 files should appear
        combined = _all_output(result)
        for i in range(4):
            assert f"file{i}.txt" in combined


# ---------------------------------------------------------------------------
# Recursive listing
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_files_env")
class TestFilesLsRecursive:
    def test_recursive_json(self, httpx_mock, runner: CliRunner) -> None:
        """Recursive listing should include _depth in JSON output."""
        root_files = [
            {
                "type": 1,
                "id": "d1",
                "name": "subdir",
                "size": 0,
                "path": "cloudreve://my/subdir",
            },
            {"type": 0, "id": "f1", "name": "root.txt", "size": 100},
        ]
        sub_files = [
            {"type": 0, "id": "f2", "name": "child.txt", "size": 200},
        ]

        # Root listing
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(root_files),
        )
        # Sub-directory listing
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2Fsubdir&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(sub_files),
        )

        result = runner.invoke(cli, ["--output", "json", "files", "ls", "--recursive"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        # subdir at depth 0, child.txt at depth 1, root.txt at depth 0
        depths = [item["_depth"] for item in data]
        assert 0 in depths
        assert 1 in depths


# ---------------------------------------------------------------------------
# URI output mode
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_files_env")
class TestFilesLsUri:
    def test_uri_flat(self, httpx_mock, runner: CliRunner) -> None:
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "--uri"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert len(lines) == 3
        assert "cloudreve://my/Documents" in lines
        assert "cloudreve://my/photo.jpg" in lines
        assert "cloudreve://my/notes.txt" in lines

    def test_uri_recursive(self, httpx_mock, runner: CliRunner) -> None:
        root_files = [
            {
                "type": 1,
                "id": "d1",
                "name": "subdir",
                "size": 0,
                "path": "cloudreve://my/subdir",
            },
            {
                "type": 0,
                "id": "f1",
                "name": "root.txt",
                "size": 100,
                "path": "cloudreve://my/root.txt",
            },
        ]
        sub_files = [
            {
                "type": 0,
                "id": "f2",
                "name": "child.txt",
                "size": 200,
                "path": "cloudreve://my/subdir/child.txt",
            },
        ]

        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(root_files),
        )
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2Fsubdir&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(sub_files),
        )

        result = runner.invoke(cli, ["files", "ls", "--recursive", "--uri"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert len(lines) == 3
        assert "cloudreve://my/subdir" in lines
        assert "cloudreve://my/subdir/child.txt" in lines
        assert "cloudreve://my/root.txt" in lines

    def test_uri_outputs_to_stdout_only(self, httpx_mock, runner: CliRunner) -> None:
        """URI mode should write only to stdout, nothing to stderr."""
        httpx_mock.add_response(
            url="https://cloud.example.com/api/v4/file?uri=cloudreve%3A%2F%2Fmy%2F&page=0&page_size=50&order_by=name&order_direction=asc",
            json=_listing_response(SAMPLE_FILES),
        )

        result = runner.invoke(cli, ["files", "ls", "--uri"])
        assert result.exit_code == 0
        assert result.output.strip()  # stdout has content
        # Each line is a valid URI
        for line in result.output.strip().splitlines():
            assert line.startswith("cloudreve://")
