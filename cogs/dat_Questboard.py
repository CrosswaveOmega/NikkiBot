from typing import Optional, ByteString
from sqlalchemy import Column, Integer, Boolean, BigInteger, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, insert, and_, or_
from database.database_singleton import DatabaseSingleton
from database.database_utils import upsert_a
from database import ensure_session
import discord
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy import Column, Integer, String, DateTime, LargeBinary
from sqlalchemy.orm import declarative_base
from database.database_main import AwareDateTime
from datetime import datetime

Base = declarative_base()


OptionalSession = Optional[AsyncSession]


## QUEST BOARD.
class Questboard(Base):
    __tablename__ = "questboard"

    id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    threshold = Column(Integer, nullable=False, default=5)
    locked = Column(Boolean, nullable=False, default=False)
    my_post =  Column(BigInteger, nullable=False)

    @classmethod
    async def get_questboard(cls, guild_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.id == guild_id)
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def add_questboard(cls, guild_id: int, channel_id: int, my_post: int):
        async with DatabaseSingleton.get_async_session() as session:
            questboard = cls(
                id=guild_id, channel_id=channel_id, my_post=my_post, locked=False
            )
            session.add(questboard)
            await session.commit()
            return questboard

    @classmethod
    async def remove_questboard(cls, guild_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.id == guild_id)
            result = await session.execute(query)
            questboard = result.scalar()
            if questboard:
                await session.delete(questboard)
                await session.commit()
                return True
            return False

    @classmethod
    async def set_my_post(cls, guild_id: int, my_post: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.id == guild_id)
            result = await session.execute(query)
            questboard = result.scalar()
            if questboard:
                questboard.my_post = my_post
                await session.commit()
                return questboard
            return None



async def setup(bot):
    DatabaseSingleton("mainsetup").load_base(Base)
