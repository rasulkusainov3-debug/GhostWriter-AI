from typing import Any

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_errors import AuthApiError
from app.core.security import decode_token
from app.db.session import fetch_one, get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if not token:
        raise AuthApiError(
            code="UNAUTHORIZED",
            message="Вы не авторизованы",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except ExpiredSignatureError as exc:
        raise AuthApiError(
            code="TOKEN_EXPIRED",
            message="Сессия истекла. Войдите снова",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    except JWTError as exc:
        raise AuthApiError(
            code="INVALID_TOKEN",
            message="Сессия недействительна. Войдите снова",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if not user_id:
        raise AuthApiError(
            code="INVALID_TOKEN",
            message="Сессия недействительна. Войдите снова",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    user = await fetch_one(session, "SELECT id, email, plan, created_at, updated_at FROM users WHERE id = :id", {"id": user_id})
    if not user:
        raise AuthApiError(
            code="UNAUTHORIZED",
            message="Вы не авторизованы",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return user
