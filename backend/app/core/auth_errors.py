from typing import Any

from fastapi import status
from starlette.exceptions import HTTPException


class AuthApiError(HTTPException):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        field: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if field:
            error["field"] = field
        if fields:
            error["fields"] = fields
        super().__init__(status_code=status_code, detail={"error": error})


def validation_error(fields: dict[str, str]) -> AuthApiError:
    return AuthApiError(
        code="VALIDATION_ERROR",
        message="Проверьте введённые данные",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        fields=fields,
    )
