from sqlalchemy.ext.asyncio import AsyncSession

from typing import Optional
from .database_singleton import DatabaseSingleton


def ensure_session(fn):
    """Ensure that a particular function is wrapped inside an async_session object."""

    async def wrapper(cls, *args, session: Optional[AsyncSession] = None, **kwargs):
        if session is None:
            async with DatabaseSingleton.get_async_session() as session:
                return await fn(cls, *args, session=session, **kwargs)
        else:
            return await fn(cls, *args, session=session, **kwargs)

    return wrapper
