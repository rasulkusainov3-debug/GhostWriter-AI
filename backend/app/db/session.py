import json
from collections.abc import AsyncGenerator, Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def _decode_value(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in ("{", "["):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _prepare_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    prepared: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if isinstance(value, (dict, list)):
            prepared[key] = json.dumps(value, ensure_ascii=False)
        else:
            prepared[key] = value
    return prepared


def row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {key: _decode_value(value) for key, value in data.items()}


async def fetch_one(session: AsyncSession, sql: str, params: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    result = await session.execute(text(sql), _prepare_params(params))
    return row_to_dict(result.mappings().first())


async def fetch_all(session: AsyncSession, sql: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), _prepare_params(params))
    return [{key: _decode_value(value) for key, value in dict(row).items()} for row in result.mappings().all()]


async def execute(session: AsyncSession, sql: str, params: Mapping[str, Any] | None = None) -> None:
    await session.execute(text(sql), _prepare_params(params))
