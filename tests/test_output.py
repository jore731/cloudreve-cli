"""Tests for output formatting utilities."""

from __future__ import annotations

import json

from cloudreve_cli.utils.output import render_json


class TestRenderJson:
    """JSON output goes to stdout."""

    def test_renders_dict(self, capsys):
        render_json({"key": "value"})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == {"key": "value"}

    def test_renders_list(self, capsys):
        render_json([1, 2, 3])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == [1, 2, 3]
