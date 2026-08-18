"""
Engine / session setup, driven entirely by settings.database_url.
Complete in the boilerplate — generic infrastructure, no business logic.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

engine = create_async_engine(settings.database_url, echo=settings.app_debug, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: `db: AsyncSession = Depends(get_db)`"""
    async with AsyncSessionLocal() as session:
        yield session
