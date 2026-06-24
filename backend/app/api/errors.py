from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError, ErrorCode, ErrorResponse


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = request.headers.get("x-request-id")
    return JSONResponse(status_code=exc.status_code, content=exc.to_response(request_id).model_dump(mode="json"))


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("x-request-id")
    body = ErrorResponse(code=ErrorCode.INTERNAL_ERROR, message="Internal server error.", request_id=request_id)
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))
