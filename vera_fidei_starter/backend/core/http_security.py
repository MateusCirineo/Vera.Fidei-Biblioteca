from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse


async def sanitize_request_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    """Do not reflect purchase credentials in FastAPI's default 422 body."""
    if request.url.path.startswith("/billing/google-play/"):
        return JSONResponse(
            status_code=422,
            content={"detail": "Dados da compra invalidos."},
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    return await request_validation_exception_handler(request, exc)
