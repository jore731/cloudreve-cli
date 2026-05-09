"""Tests for the HTTP client wrapper."""

from __future__ import annotations

import pytest

from cloudreve_cli.client import CloudreveClient
from cloudreve_cli.exceptions import APIError, AuthError, CloudreveError, NotFoundError


def _envelope(data, *, code=0, msg=""):
    """Build a Cloudreve API response envelope."""
    return {"code": code, "data": data, "msg": msg, "error": None, "correlation_id": None}


class TestEnvelopeParsing:
    """Response envelope extraction."""

    def test_success_extracts_data(self, httpx_mock):
        httpx_mock.add_response(json=_envelope({"version": "4.0.0"}))
        with CloudreveClient(server="https://example.com") as c:
            result = c.get("/api/v4/site/ping")
        assert result == {"version": "4.0.0"}

    def test_nonzero_code_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(json=_envelope(None, code=40001, msg="Bad request"))
        with (
            CloudreveClient(server="https://example.com") as c,
            pytest.raises(APIError, match="Bad request"),
        ):
            c.get("/api/v4/test")

    def test_raw_mode_returns_full_body(self, httpx_mock):
        body = _envelope({"version": "4.0.0"})
        httpx_mock.add_response(json=body)
        with CloudreveClient(server="https://example.com") as c:
            result = c.get("/api/v4/site/ping", raw=True)
        assert result == body


class TestHTTPErrors:
    """HTTP status code mapping to exceptions."""

    def test_401_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(
            status_code=401,
            json={"msg": "Unauthorized", "code": 401},
        )
        with (
            CloudreveClient(server="https://example.com") as c,
            pytest.raises(AuthError, match="Unauthorized"),
        ):
            c.get("/api/v4/test")

    def test_404_raises_not_found(self, httpx_mock):
        httpx_mock.add_response(
            status_code=404,
            json={"msg": "Not found", "code": 404},
        )
        with (
            CloudreveClient(server="https://example.com") as c,
            pytest.raises(NotFoundError, match="Not found"),
        ):
            c.get("/api/v4/test")

    def test_500_without_retries_raises(self, httpx_mock):
        httpx_mock.add_response(status_code=500, text="Internal Server Error")
        with (
            CloudreveClient(server="https://example.com", retries=0) as c,
            pytest.raises(CloudreveError, match="Server error 500"),
        ):
            c.get("/api/v4/test")


class TestRetries:
    """Retry behavior on 5xx."""

    def test_retries_on_500_then_succeeds(self, httpx_mock):
        httpx_mock.add_response(status_code=500, text="fail")
        httpx_mock.add_response(json=_envelope("ok"))
        with CloudreveClient(server="https://example.com", retries=1) as c:
            result = c.get("/api/v4/test")
        assert result == "ok"

    def test_no_retry_on_4xx(self, httpx_mock):
        httpx_mock.add_response(
            status_code=400,
            json={"msg": "Bad request", "code": 400},
        )
        with (
            CloudreveClient(server="https://example.com", retries=3) as c,
            pytest.raises(CloudreveError, match="Bad request"),
        ):
            c.get("/api/v4/test")
        # Should have made exactly 1 request, not 4
        assert len(httpx_mock.get_requests()) == 1


class TestAuth:
    """Authorization header handling."""

    def test_bearer_token_sent(self, httpx_mock):
        httpx_mock.add_response(json=_envelope("ok"))
        with CloudreveClient(server="https://example.com", token="my-jwt") as c:
            c.get("/api/v4/test")
        req = httpx_mock.get_requests()[0]
        assert req.headers["authorization"] == "Bearer my-jwt"

    def test_no_auth_header_when_no_token(self, httpx_mock):
        httpx_mock.add_response(json=_envelope("ok"))
        with CloudreveClient(server="https://example.com") as c:
            c.get("/api/v4/test")
        req = httpx_mock.get_requests()[0]
        assert "authorization" not in req.headers
