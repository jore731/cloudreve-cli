"""Tests for cloudreve_cli.utils.uri."""

from __future__ import annotations

import pytest

from cloudreve_cli.utils.uri import CloudreveURI, build_uri, parse_uri

# ---------------------------------------------------------------------------
# parse_uri — shorthand paths
# ---------------------------------------------------------------------------


class TestParseShorthand:
    def test_absolute_path(self) -> None:
        result = parse_uri("/photos")
        assert result == CloudreveURI(host="my", path="/photos")

    def test_relative_path(self) -> None:
        result = parse_uri("photos")
        assert result == CloudreveURI(host="my", path="/photos")

    def test_nested_path(self) -> None:
        result = parse_uri("/photos/2024/vacation")
        assert result == CloudreveURI(host="my", path="/photos/2024/vacation")

    def test_root_path(self) -> None:
        result = parse_uri("/")
        assert result == CloudreveURI(host="my", path="/")

    def test_bare_slash(self) -> None:
        result = parse_uri("/")
        assert result.to_uri() == "cloudreve://my/"

    def test_whitespace_stripped(self) -> None:
        result = parse_uri("  /photos  ")
        assert result == CloudreveURI(host="my", path="/photos")

    def test_relative_becomes_absolute(self) -> None:
        """Bare path like 'trash/old' is NOT the trash host — it's a subfolder."""
        result = parse_uri("trash/old")
        assert result == CloudreveURI(host="my", path="/trash/old")


# ---------------------------------------------------------------------------
# parse_uri — full cloudreve:// URIs
# ---------------------------------------------------------------------------


class TestParseFullURI:
    def test_my_host(self) -> None:
        result = parse_uri("cloudreve://my/photos")
        assert result.host == "my"
        assert result.path == "/photos"

    def test_trash_host(self) -> None:
        result = parse_uri("cloudreve://trash/old-file.txt")
        assert result.host == "trash"
        assert result.path == "/old-file.txt"

    def test_shared_host(self) -> None:
        result = parse_uri("cloudreve://shared_with_me/")
        assert result.host == "shared_with_me"
        assert result.path == "/"

    def test_user_at_host(self) -> None:
        result = parse_uri("cloudreve://luPa@my/docs")
        assert result.host == "my"
        assert result.user == "luPa"
        assert result.path == "/docs"

    def test_query_params(self) -> None:
        result = parse_uri("cloudreve://my/photos?category=image&type=file")
        assert result.host == "my"
        assert result.path == "/photos"
        assert result.query == {"category": "image", "type": "file"}

    def test_invalid_host(self) -> None:
        with pytest.raises(ValueError, match="Invalid URI host"):
            parse_uri("cloudreve://invalid_host/path")

    def test_root_my(self) -> None:
        result = parse_uri("cloudreve://my/")
        assert result.host == "my"
        assert result.path == "/"


# ---------------------------------------------------------------------------
# CloudreveURI.to_uri
# ---------------------------------------------------------------------------


class TestToURI:
    def test_simple(self) -> None:
        uri = CloudreveURI(host="my", path="/photos")
        assert uri.to_uri() == "cloudreve://my/photos"

    def test_with_user(self) -> None:
        uri = CloudreveURI(host="my", user="admin", path="/docs")
        assert uri.to_uri() == "cloudreve://admin@my/docs"

    def test_with_query(self) -> None:
        uri = CloudreveURI(host="my", path="/", query={"category": "image"})
        assert uri.to_uri() == "cloudreve://my/?category=image"

    def test_special_chars_in_path(self) -> None:
        uri = CloudreveURI(host="my", path="/my folder/file (1).txt")
        result = uri.to_uri()
        assert "my%20folder" in result
        assert "file%20%281%29.txt" in result

    def test_roundtrip(self) -> None:
        original = "cloudreve://my/photos"
        result = parse_uri(original)
        assert result.to_uri() == original


# ---------------------------------------------------------------------------
# build_uri
# ---------------------------------------------------------------------------


class TestBuildURI:
    def test_simple(self) -> None:
        assert build_uri("/photos") == "cloudreve://my/photos"

    def test_with_host(self) -> None:
        assert build_uri("/old", host="trash") == "cloudreve://trash/old"

    def test_with_user(self) -> None:
        result = build_uri("/docs", host="my", user="admin")
        assert result == "cloudreve://admin@my/docs"

    def test_with_query(self) -> None:
        result = build_uri("/", query={"name": "test"})
        assert result == "cloudreve://my/?name=test"

    def test_path_normalization(self) -> None:
        """Path without leading slash gets one added."""
        assert build_uri("photos") == "cloudreve://my/photos"
