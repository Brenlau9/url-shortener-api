from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str


STATUS_TO_ERROR_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    410: "GONE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
}


def normalize_http_exception(exc: HTTPException) -> ApiError:
    """
    Converts HTTPException.detail into (code, message).

    Supports:
    - detail as str -> message=str, code inferred from status
    - detail as {"code": "...", "message": "..."} -> use directly
    - detail as {"error": {"code": "...", "message": "..."}} -> use directly
    """
    status = exc.status_code
    default_code = STATUS_TO_ERROR_CODE.get(status, "ERROR")

    detail: Any = exc.detail
    if isinstance(detail, dict):
        if "error" in detail and isinstance(detail["error"], dict):
            inner = detail["error"]
            if "code" in inner and "message" in inner:
                return ApiError(code=str(inner["code"]), message=str(inner["message"]))
        if "code" in detail and "message" in detail:
            return ApiError(code=str(detail["code"]), message=str(detail["message"]))

    # fallback
    msg = detail if isinstance(detail, str) else "Request failed"
    return ApiError(code=default_code, message=str(msg))
