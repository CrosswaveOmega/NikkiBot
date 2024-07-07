from sqlalchemy import Column, Integer, Boolean, BigInteger, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_singleton import DatabaseSingleton
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Starboard(Base):
    __tablename__ = "starboard"

    id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    threshold = Column(Integer, nullable=False, default=5)
    locked = Column(Boolean, nullable=False, default=False)

    @classmethod
    async def get_starboard(cls, guild_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.id == guild_id)
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def add_starboard(cls, guild_id: int, channel_id: int, threshold: int):
        async with DatabaseSingleton.get_async_session() as session:
            starboard = cls(
                id=guild_id, channel_id=channel_id, threshold=threshold, locked=False
            )
            session.add(starboard)
            await session.commit()
            return starboard

    @classmethod
    async def remove_starboard(cls, guild_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.id == guild_id)
            result = await session.execute(query)
            starboard = result.scalar()
            if starboard:
                await session.delete(starboard)
                await session.commit()
                return True
            return False

    @classmethod
    async def set_threshold(cls, guild_id: int, threshold: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.id == guild_id)
            result = await session.execute(query)
            starboard = result.scalar()
            if starboard:
                starboard.threshold = threshold
                await session.commit()
                return starboard
            return None


class StarboardEntryTable(Base):
    __tablename__ = "starboard_entry"
    message_id = Column(BigInteger, nullable=False, primary_key=True)
    channel_id = Column(BigInteger, nullable=True)
    guild_id = Column(
        BigInteger,
        nullable=False,
        primary_key=True,
    )
    author_id = Column(BigInteger, nullable=True)
    bot_message = Column(BigInteger, nullable=True, default=None)
    bot_message_url = Column(String, nullable=True, default=None)

    message_url = Column(String, nullable=True, default=None)
    total = Column(Integer, nullable=False, default=0)

    @classmethod
    async def get_entry(cls, guild_id: int, message_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                cls.message_id == message_id, cls.guild_id == guild_id
            )
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def add_or_update_entry(
        cls,
        guild_id: int,
        message_id: int,
        channel_id: int,
        author_id: int,
        message_url: str,
        op: int = 1,
    ):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                cls.message_id == message_id, cls.guild_id == guild_id
            )
            result = await session.execute(query)
            entry = result.scalar()
            if entry:
                entry.total += op
            else:
                entry = cls(
                    message_id=message_id,
                    channel_id=channel_id,
                    guild_id=guild_id,
                    author_id=author_id,
                    message_url=message_url,
                    total=1,
                )
                session.add(entry)
            await session.commit()
            return entry

    @classmethod
    async def add_or_update_bot_message(
        cls, guild_id: int, message_id: int, bot_message_id: int, bot_message_url: str
    ):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                cls.message_id == message_id, cls.guild_id == guild_id
            )
            result = await session.execute(query)
            entry = result.scalar()
            if entry:
                entry.bot_message = bot_message_id
                entry.bot_message_url = bot_message_url
            else:
                entry = cls(
                    message_id=message_id, guild_id=guild_id, bot_message=bot_message_id
                )
                session.add(entry)
            await session.commit()
            return entry

    @classmethod
    async def delete_entry_by_bot_message_url(cls, bot_message_url: str):
        async with DatabaseSingleton.get_async_session() as session:
            result = await session.execute(
                select(cls).where(cls.bot_message_url == bot_message_url)
            )
            entry = result.scalar()
            if entry:
                await session.delete(entry)
                await session.commit()
                return True
            return False

    @classmethod
    async def get_with_url(cls, bot_message_url: str):
        async with DatabaseSingleton.get_async_session() as session:
            result = await session.execute(
                select(cls).where(cls.bot_message_url == bot_message_url)
            )
            entry = result.scalar()
            return entry


async def setup(bot):
    DatabaseSingleton("mainsetup").load_base(Base)
