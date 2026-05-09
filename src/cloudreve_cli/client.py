"""HTTP client wrapper for the Cloudreve v4 API.

Handles:
- Bearer token auth
- API response envelope parsing ({code, data, msg, error, correlation_id})
- Automatic token refresh on 401 (if refresh_token is available)
- Retries with exponential backoff on 5xx / connection errors
- Verbose logging to stderr
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any

import httpx

from cloudreve_cli.exceptions import APIError, AuthError, CloudreveError, NotFoundError


def _log_verbose(method: str, url: str, status: int, elapsed_ms: float) -> None:
    print(f"  {method} {url} → {status} ({elapsed_ms:.0f}ms)", file=sys.stderr)


class CloudreveClient:
    """Thin wrapper around httpx for Cloudreve v4 API calls."""

    def __init__(
        self,
        *,
        server: str,
        token: str | None = None,
        refresh_token: str | None = None,
        retries: int = 0,
        verbose: bool = False,
        timeout: float = 30.0,
        on_token_refresh: Callable[[str, str], None] | None = None,
    ):
        base_url = server.rstrip("/")
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._http = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )
        self._retries = retries
        self._verbose = verbose
        self._refresh_token = refresh_token
        self._on_token_refresh = on_token_refresh
        self._refreshing = False

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> CloudreveClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- public API ---

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        """Make an API request with automatic token refresh on 401."""
        try:
            return self._do_request(
                method, path, params=params, json=json, data=data, headers=headers, raw=raw
            )
        except AuthError:
            if self._refreshing or not self._refresh_token:
                raise
            # Try auto-refresh and retry once
            self._do_auto_refresh()
            return self._do_request(
                method, path, params=params, json=json, data=data, headers=headers, raw=raw
            )

    def _do_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        """Make an API request, parse envelope, return `data` field.

        If *raw* is True, return the full parsed JSON without envelope extraction.
        """
        last_exc: Exception | None = None
        attempts = 1 + self._retries

        for attempt in range(attempts):
            if attempt > 0:
                backoff = min(2**attempt, 30)
                time.sleep(backoff)

            try:
                t0 = time.monotonic()
                resp = self._http.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    data=data,
                    headers=headers,
                )
                elapsed_ms = (time.monotonic() - t0) * 1000

                if self._verbose:
                    _log_verbose(method, str(resp.url), resp.status_code, elapsed_ms)

            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    continue
                raise CloudreveError(f"Connection error: {exc}") from exc

            # Never retry 4xx
            if 400 <= resp.status_code < 500:
                return self._handle_client_error(resp)

            # Retry 5xx
            if resp.status_code >= 500:
                last_exc = CloudreveError(f"Server error {resp.status_code}: {resp.text[:200]}")
                if attempt < attempts - 1:
                    continue
                raise last_exc

            # Success path
            if raw:
                return resp.json()

            return self._parse_envelope(resp)

        # Should not reach here, but just in case
        raise last_exc or CloudreveError("Request failed")  # pragma: no cover

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    # --- internal ---

    def _do_auto_refresh(self) -> None:
        """Attempt to refresh the access token using the refresh token."""
        self._refreshing = True
        try:
            resp = self._http.post(
                "/api/v4/session/token/refresh",
                json={"refresh_token": self._refresh_token},
            )
            if resp.status_code != 200:
                raise AuthError("Token refresh failed — please log in again.")

            body = resp.json()
            if body.get("code", -1) != 0:
                raise AuthError("Token refresh failed — please log in again.")

            data = body["data"]
            new_access = data["access_token"]
            new_refresh = data["refresh_token"]

            # Update client state
            self._http.headers["Authorization"] = f"Bearer {new_access}"
            self._refresh_token = new_refresh

            if self._on_token_refresh:
                self._on_token_refresh(new_access, new_refresh)
        finally:
            self._refreshing = False

    @staticmethod
    def _parse_envelope(resp: httpx.Response) -> Any:
        """Extract `data` from {code, data, msg, error, correlation_id}."""
        body = resp.json()

        code = body.get("code", -1)
        if code != 0:
            msg = body.get("msg") or body.get("error") or f"API error (code={code})"
            # Envelope auth errors (401/403) must raise AuthError so the
            # auto-refresh logic in request() can intercept them.
            if code in (401, 403):
                raise AuthError(str(msg))
            raise APIError(
                str(msg),
                code=code,
                correlation_id=body.get("correlation_id"),
            )

        return body.get("data")

    @staticmethod
    def _handle_client_error(resp: httpx.Response) -> Any:
        """Map 4xx HTTP status to appropriate exception."""
        try:
            body = resp.json()
            msg = body.get("msg") or body.get("error") or resp.text[:200]
        except Exception:
            msg = resp.text[:200]

        if resp.status_code in (401, 403):
            raise AuthError(str(msg))
        if resp.status_code == 404:
            raise NotFoundError(str(msg))
        if resp.status_code == 409:
            from cloudreve_cli.exceptions import ConflictError

            raise ConflictError(str(msg))
        raise CloudreveError(f"HTTP {resp.status_code}: {msg}")
