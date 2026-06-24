from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_REQUIRED = "authentication_required"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class AppError(Exception):
    status_code = 500
    code = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        *,
        details: list[ErrorDetail] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
        self.metadata = metadata or {}

    def to_response(self, request_id: str | None = None) -> ErrorResponse:
        details = list(self.details)
        if self.metadata:
            details.append(ErrorDetail(message="Additional error context.", metadata=self.metadata))
        return ErrorResponse(code=self.code, message=self.message, details=details, request_id=request_id)


class ValidationAppError(AppError):
    status_code = 422
    code = ErrorCode.VALIDATION_ERROR


class AuthenticationRequiredError(AppError):
    status_code = 401
    code = ErrorCode.AUTHENTICATION_REQUIRED


class PermissionDeniedError(AppError):
    status_code = 403
    code = ErrorCode.PERMISSION_DENIED


class NotFoundError(AppError):
    status_code = 404
    code = ErrorCode.NOT_FOUND


class ConflictError(AppError):
    status_code = 409
    code = ErrorCode.CONFLICT


class InvalidStateTransitionError(ConflictError):
    code = ErrorCode.INVALID_STATE_TRANSITION


class ExternalServiceError(AppError):
    status_code = 502
    code = ErrorCode.EXTERNAL_SERVICE_ERROR
