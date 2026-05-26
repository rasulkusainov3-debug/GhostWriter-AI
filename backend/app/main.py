from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routers import analytics, assets, auth, chat, content_plans, generated_posts, integrations, lifecycle, onboarding, profiles, publisher, scheduled_posts, social_accounts, social_parser, trends, users
from app.core.auth_errors import AuthApiError
from app.core.config import settings

app = FastAPI(title=settings.project_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthApiError)
async def auth_error_handler(_, exc: AuthApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


def _http_error_code(status_code: int) -> str:
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 422:
        return "VALIDATION_ERROR"
    return "REQUEST_FAILED"


@app.exception_handler(HTTPException)
async def http_error_handler(_, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": _http_error_code(exc.status_code),
                "message": message,
                "field": None,
                "fields": {},
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for error in exc.errors():
        loc = [str(part) for part in error.get("loc", []) if part != "body"]
        key = ".".join(loc) if loc else "body"
        fields[key] = str(error.get("msg") or "Invalid value")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Проверьте введённые данные",
                "field": None,
                "fields": fields,
            }
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": settings.project_name}


app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(social_parser.router, prefix="/api")
app.include_router(trends.router, prefix="/api")
app.include_router(content_plans.router, prefix="/api")
app.include_router(generated_posts.router, prefix="/api")
app.include_router(social_accounts.router, prefix="/api")
app.include_router(scheduled_posts.router, prefix="/api")
app.include_router(publisher.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(lifecycle.router, prefix="/api")
