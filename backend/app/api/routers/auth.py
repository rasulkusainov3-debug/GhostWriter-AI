import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.auth_errors import AuthApiError, validation_error
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import execute, fetch_one, get_session
from app.schemas.common import ApiMessage, LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def password_errors(password: str) -> str | None:
    if len(password) < 8:
        return "Пароль должен содержать минимум 8 символов"
    if not re.search(r"[A-Za-zА-Яа-я]", password) or not re.search(r"\d", password):
        return "Пароль должен содержать хотя бы одну букву и одну цифру"
    return None


def validate_register_payload(payload: RegisterRequest) -> tuple[str, str, str, list[str]]:
    fields: dict[str, str] = {}
    name = payload.name.strip()
    username = (payload.username or "").strip()
    email = payload.email.strip().lower()
    password = payload.password
    social_links = [link.strip() for link in payload.social_links if link.strip()]

    if not name:
        fields["name"] = "Имя не может быть пустым"
    if not username:
        fields["username"] = "Введите логин"
    if not email:
        fields["email"] = "Введите email"
    elif not EMAIL_RE.match(email):
        fields["email"] = "Введите корректный email"
    if not password:
        fields["password"] = "Введите пароль"
    else:
        weak_password = password_errors(password)
        if weak_password:
            fields["password"] = weak_password
    if payload.password_confirm is not None and password != payload.password_confirm:
        fields["password_confirm"] = "Пароли не совпадают"
    if any(not is_valid_url(link) for link in social_links):
        fields["social"] = "Ссылки на соцсети должны быть корректными URL"

    if fields:
        raise validation_error(fields)
    return name, username, email, social_links


def validate_login_payload(payload: LoginRequest) -> tuple[str, str]:
    fields: dict[str, str] = {}
    login = payload.email.strip().lower()
    password = payload.password
    if not login:
        fields["email"] = "Введите email или логин"
    if not password:
        fields["password"] = "Введите пароль"
    if fields:
        raise validation_error(fields)
    return login, password


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    name, username, email, social_links = validate_register_payload(payload)

    existing_email = await fetch_one(session, "SELECT id FROM users WHERE lower(email) = :email", {"email": email})
    if existing_email:
        raise AuthApiError(
            code="USER_ALREADY_EXISTS",
            message="Пользователь с таким email уже существует",
            status_code=status.HTTP_409_CONFLICT,
            field="email",
        )

    existing_username = await fetch_one(
        session,
        "SELECT id FROM user_profiles WHERE lower(raw_answers->>'username') = :username",
        {"username": username.lower()},
    )
    if existing_username:
        raise AuthApiError(
            code="USERNAME_ALREADY_EXISTS",
            message="Пользователь с таким логином уже существует",
            status_code=status.HTTP_409_CONFLICT,
            field="username",
        )

    try:
        user = await fetch_one(
            session,
            """
            INSERT INTO users (email, password_hash, plan)
            VALUES (:email, :password_hash, :plan)
            RETURNING id, email, plan, created_at, updated_at
            """,
            {"email": email, "password_hash": hash_password(payload.password), "plan": payload.plan},
        )
        await execute(
            session,
            """
            INSERT INTO user_profiles (user_id, name, raw_answers, platforms)
            VALUES (:user_id, :name, CAST(:raw_answers AS JSONB), CAST(:platforms AS JSONB))
            """,
            {
                "user_id": user["id"],
                "name": name,
                "raw_answers": {"username": username, "social_links": social_links, **payload.optional_profile},
                "platforms": [],
            },
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AuthApiError(
            code="USER_ALREADY_EXISTS",
            message="Пользователь с таким email уже существует",
            status_code=status.HTTP_409_CONFLICT,
            field="email",
        ) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise AuthApiError(
            code="SERVER_ERROR",
            message="Не удалось создать аккаунт. Попробуйте позже",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    return TokenResponse(access_token=create_access_token(str(user["id"])), user=user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    login_value, password = validate_login_payload(payload)
    user = await fetch_one(
        session,
        """
        SELECT users.*
        FROM users
        LEFT JOIN user_profiles ON user_profiles.user_id = users.id
        WHERE lower(users.email) = :login
           OR lower(user_profiles.raw_answers->>'username') = :login
        """,
        {"login": login_value},
    )
    if not user:
        raise AuthApiError(
            code="USER_NOT_FOUND",
            message="Пользователь не найден",
            status_code=status.HTTP_401_UNAUTHORIZED,
            field="email",
        )
    if not verify_password(password, user.get("password_hash")):
        raise AuthApiError(
            code="INVALID_PASSWORD",
            message="Неверный пароль",
            status_code=status.HTTP_401_UNAUTHORIZED,
            field="password",
        )
    public_user = {key: user[key] for key in ["id", "email", "plan", "created_at", "updated_at"]}
    return TokenResponse(access_token=create_access_token(str(user["id"])), user=public_user)


@router.post("/logout", response_model=ApiMessage)
async def logout() -> ApiMessage:
    return ApiMessage(message="Client should discard the bearer token")


@router.get("/me")
async def me(user: dict = Depends(current_user)) -> dict:
    return user
