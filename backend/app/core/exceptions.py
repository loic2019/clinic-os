"""
Application-wide exceptions and their FastAPI handlers.

All API errors are returned using the standard CLINIC OS envelope:

{
  "success": false,
  "error": { "code": "...", "message": "..." }
}
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ClinicOSException(Exception):
    """Base exception for all CLINIC OS domain errors."""

    code: str = "ERROR"
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, code: str | None = None, status_code: int | None = None):
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        super().__init__(message)


class NotFoundError(ClinicOSException):
    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenError(ClinicOSException):
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN


class UnauthorizedError(ClinicOSException):
    code = "UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED


class ConflictError(ClinicOSException):
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT


def _error_envelope(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ClinicOSException)
    async def clinic_os_exception_handler(request: Request, exc: ClinicOSException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_envelope("VALIDATION_ERROR", "Invalid request data."),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
