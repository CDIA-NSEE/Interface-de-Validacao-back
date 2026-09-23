from __future__ import annotations


class DomainError(Exception):
    """Base class for framework-agnostic errors raised by the service layer."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ValidationError(DomainError):
    """Raised when input fails a business rule (maps to HTTP 400)."""


class NotFoundError(DomainError):
    """Raised when a requested aggregate does not exist (maps to HTTP 404)."""


class ForbiddenError(DomainError):
    """Raised when an action is not permitted for the current user (maps to HTTP 403)."""


class UnauthorizedError(DomainError):
    """Raised when authentication fails (maps to HTTP 401)."""
