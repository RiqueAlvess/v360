from typing import Any


class DomainException(Exception):
    """Base exception for all domain-level errors."""

    status_code: int = 500
    detail: str = "An unexpected domain error occurred."

    def __init__(self, detail: str | None = None, **context: Any) -> None:
        self.detail = detail or self.__class__.detail
        self.context: dict[str, Any] = context
        super().__init__(self.detail)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(detail={self.detail!r}, context={self.context!r})"


class NotFoundError(DomainException):
    """Raised when a requested resource does not exist."""

    status_code: int = 404
    detail: str = "Resource not found."

    def __init__(self, resource: str = "Resource", resource_id: Any = None) -> None:
        detail = f"{resource} not found."
        if resource_id is not None:
            detail = f"{resource} with id '{resource_id}' not found."
        super().__init__(detail=detail, resource=resource, resource_id=resource_id)


class UnauthorizedError(DomainException):
    """Raised when a request lacks valid authentication credentials."""

    status_code: int = 401
    detail: str = "Authentication required."

    def __init__(self, detail: str = "Authentication required.") -> None:
        super().__init__(detail=detail)


class ForbiddenError(DomainException):
    """Raised when an authenticated user lacks permission for the requested action."""

    status_code: int = 403
    detail: str = "You do not have permission to perform this action."

    def __init__(self, detail: str = "You do not have permission to perform this action.") -> None:
        super().__init__(detail=detail)


class ValidationError(DomainException):
    """Raised when domain-level business rule validation fails."""

    status_code: int = 422
    detail: str = "Validation failed."

    def __init__(self, detail: str = "Validation failed.", field: str | None = None) -> None:
        super().__init__(detail=detail, field=field)


class ConflictError(DomainException):
    """Raised when an operation conflicts with the current state of the resource."""

    status_code: int = 409
    detail: str = "Resource conflict."

    def __init__(self, detail: str = "Resource conflict.") -> None:
        super().__init__(detail=detail)
