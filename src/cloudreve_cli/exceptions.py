"""Custom exceptions with associated exit codes."""

from cloudreve_cli import exit_codes


class CloudreveError(Exception):
    """Base exception for cloudreve-cli errors."""

    exit_code: int = exit_codes.GENERAL_ERROR

    def __init__(self, message: str, *, exit_code: int | None = None):
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class AuthError(CloudreveError):
    """Authentication or authorization failure."""

    exit_code = exit_codes.AUTH_ERROR


class NotFoundError(CloudreveError):
    """Requested resource was not found."""

    exit_code = exit_codes.NOT_FOUND


class ConflictError(CloudreveError):
    """Conflict with current server state."""

    exit_code = exit_codes.CONFLICT


class APIError(CloudreveError):
    """Error returned by the Cloudreve API envelope."""

    def __init__(self, message: str, *, code: int, correlation_id: str | None = None):
        super().__init__(message)
        self.api_code = code
        self.correlation_id = correlation_id
