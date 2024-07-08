from typing import Optional
from sqlalchemy import Column, Integer, Boolean, BigInteger, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, insert
from database.database_singleton import DatabaseSingleton
from database.database_utils import upsert_a
from database import ensure_session
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


OptionalSession = Optional[AsyncSession]


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
    @ensure_session
    async def get_entry(
        cls, guild_id: int, message_id: int, session: OptionalSession = None
    ):
        query = select(cls).where(
            cls.message_id == message_id, cls.guild_id == guild_id
        )
        result = await session.execute(query)
        return result.scalar()

    @classmethod
    @ensure_session
    async def get_entries_by_guild(cls, guild_id: int, session: OptionalSession = None):
        query = select(cls).where(cls.guild_id == guild_id)
        result = await session.execute(query)
        return result.scalars().all()

    @classmethod
    @ensure_session
    async def add_or_update_entry(
        cls,
        guild_id: int,
        message_id: int,
        channel_id: int,
        author_id: int,
        message_url: str,
        op: int = 1,
        session: OptionalSession = None,
    ):
        query = select(cls).where(
            cls.message_id == message_id, cls.guild_id == guild_id
        )
        result = await session.execute(query)
        entry = result.scalar()

        print("entry", entry, message_id, guild_id, message_url)
        if entry:
            print("session", session)
            entry.total = await StarboardEntryGivers.count_starrers(
                guild_id, message_id, session=session
            )
        else:
            entry = cls(
                message_id=message_id,
                channel_id=channel_id,
                guild_id=guild_id,
                author_id=author_id,
                message_url=message_url,
                total=await StarboardEntryGivers.count_starrers(
                    guild_id, message_id, session=session
                ),
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

    def __str__(self):
        return f"StarboardEntryTable(message_id={self.message_id}, channel_id={self.channel_id}, guild_id={self.guild_id}, author_id={self.author_id}, bot_message={self.bot_message}, bot_message_url={self.bot_message_url}, message_url={self.message_url}, total={self.total})"


class StarboardEntryGivers(Base):
    __tablename__ = "star_giver_table"
    message_id = Column(BigInteger, nullable=False, primary_key=True)
    guild_id = Column(BigInteger, nullable=False, primary_key=True)
    star_giver_id = Column(BigInteger, nullable=False, primary_key=True)
    source_message_url = Column(String, nullable=True, default=None)
    emoji = Column(String, nullable=True, default=None)

    @classmethod
    async def get_starrers(cls, guild_id: int, message_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                cls.message_id == message_id, cls.guild_id == guild_id
            )
            result = await session.execute(query)
            return result.scalars().all()

    @classmethod
    @ensure_session
    async def get_starrer(
        cls,
        guild_id: int,
        message_id: int,
        star_giver_id: int,
        session: OptionalSession = None,
    ):
        query = select(cls).where(
            cls.message_id == message_id,
            cls.guild_id == guild_id,
            cls.star_giver_id == star_giver_id,
        )
        result = await session.execute(query)
        return result.scalar()

    @classmethod
    async def count_starrers(
        cls, guild_id: int, message_id: int, session: OptionalSession = None
    ):
        query = select(func.count(cls.star_giver_id)).where(
            cls.message_id == message_id, cls.guild_id == guild_id
        )
        result = await session.execute(query)
        return result.scalar()

    @classmethod
    async def add_starrers_bulk(
        cls,
        starrers: list[tuple[int, int, int, str, str]],
        session: OptionalSession = None,
    ):
        new_starrers = [
            {
                "message_id": message_id,
                "guild_id": guild_id,
                "star_giver_id": star_giver_id,
                "emoji": emoji,
                "source_message_url": source_message_url,
            }
            for message_id, guild_id, star_giver_id, emoji, source_message_url in starrers
        ]
        await upsert_a(
            session,
            cls,
            ["message_id", "guild_id", "star_giver_id"],
            new_starrers,
            do_commit=False,
        )

    @classmethod
    async def add_starrer(
        cls,
        message_id: int,
        guild_id: int,
        star_giver_id: int,
        emoji: str = None,
        source_message_url: str = None,
    ):
        async with DatabaseSingleton.get_async_session() as session:
            # Check if the starrer already exists
            new_starrers = [
                {
                    "message_id": message_id,
                    "guild_id": guild_id,
                    "star_giver_id": star_giver_id,
                    "emoji": emoji,
                    "source_message_url": source_message_url,
                }
            ]

            await upsert_a(
                session, cls, ["message_id", "guild_id", "star_giver_id"], new_starrers
            )

    @classmethod
    @ensure_session
    async def remove_starrer(
        cls,
        message_id: int,
        guild_id: int,
        star_giver_id: int = None,
        session: OptionalSession = None,
    ):
        async with DatabaseSingleton.get_async_session() as session:
            if star_giver_id:
                # Remove a specific star giver entry
                stmt = delete(cls).where(
                    cls.message_id == message_id,
                    cls.guild_id == guild_id,
                    cls.star_giver_id == star_giver_id,
                )
            else:
                # Remove all star givers for the message_id and guild_id combination
                stmt = delete(cls).where(
                    cls.message_id == message_id, cls.guild_id == guild_id
                )
            await session.execute(stmt)
            await session.commit()


async def setup(bot):
    DatabaseSingleton("mainsetup").load_base(Base)
