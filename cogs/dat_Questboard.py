from typing import Optional, ByteString
from sqlalchemy import Column, Integer, Boolean, BigInteger, String, Float
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

    id = Column(BigInteger, primary_key=True)  # Server ID
    channel_id = Column(BigInteger, nullable=False)  # Guild Channel ID
    threshold = Column(Integer, nullable=False, default=5)
    locked = Column(Boolean, nullable=False, default=False)
    my_post = Column(BigInteger, nullable=False)  # My Post

    @classmethod
    async def get_id_channel_id_pairs(cls):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls.id, cls.channel_id)
            result = await session.execute(query)
            return result.all()

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


class QuestLeaderboard(Base):
    __tablename__ = "quest_leaderboard_table"

    guild_id = Column(BigInteger, nullable=False, primary_key=True)  # Guild server ID
    user_id = Column(BigInteger, nullable=False, primary_key=True)  # User ID
    score = Column(Integer, nullable=False, default=0)  # User's score
    thank_count = Column(
        Integer, nullable=False, default=0
    )  # Number of thank-yous received
    quests_participated = Column(
        Integer, nullable=False, default=0
    )  # Number of quests participated in
    additional_field_1 = Column(
        Integer, nullable=True
    )  # Example of an additional field
    additional_field_2 = Column(
        Integer, nullable=True
    )  # Another additional field (if needed)
    messages_sent = Column(
        Integer, nullable=True, default=0
    )  # messages sent in a quest board.
    files_sent = Column(
        Integer, nullable=True, default=0
    )  # files sent in a quest board.

    @classmethod
    async def get_leaderboard_for_guild(cls, guild_id: int,limit=40):
        async with DatabaseSingleton.get_async_session() as session:
            query = (
                select(cls)
                .where(cls.guild_id == guild_id)
                .order_by(cls.score.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return result.scalars().all()

    @classmethod
    async def get_user_leaderboard_entry(cls, guild_id: int, user_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                and_(cls.guild_id == guild_id, cls.user_id == user_id)
            )
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def update_user_score(
        cls,
        guild_id: int,
        user_id: int,
        score: int = 0,
        thank_count: int = 0,
        quests_participated: int = 0,
        messages: int = 0,
        files: int = 0,
    ):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                and_(cls.guild_id == guild_id, cls.user_id == user_id)
            )
            result = await session.execute(query)
            leaderboard_entry = result.scalar()

            if leaderboard_entry:
                leaderboard_entry.score += score
                leaderboard_entry.thank_count += thank_count
                leaderboard_entry.quests_participated += quests_participated
                if leaderboard_entry.messages_sent == None:
                    leaderboard_entry.messages_sent = 0
                if leaderboard_entry.files_sent == None:
                    leaderboard_entry.files_sent = 0
                leaderboard_entry.messages_sent += messages
                leaderboard_entry.files_sent += files

                await session.commit()
                return leaderboard_entry
            else:
                leaderboard_entry = cls(
                    guild_id=guild_id,
                    user_id=user_id,
                    score=score,
                    thank_count=thank_count,
                    quests_participated=quests_participated,
                    messages_sent=messages,
                    files_sent=files,
                )
                session.add(leaderboard_entry)
                await session.commit()
                return leaderboard_entry


class QuestRoleConfig(Base):
    __tablename__ = "quest_role_config_table"

    guild_id = Column(BigInteger, nullable=False, primary_key=True)  # Guild server ID
    role_id = Column(BigInteger, nullable=False, primary_key=True)  # Id for Role
    score_bonus = Column(
        Float, nullable=False, default=1.0
    )  # score mod for quests made by this role.
    kudos_bonus = Column(Float, nullable=False, default=1.0)

    @classmethod
    async def get_all_role_specials_for_guild(cls, guild_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            rolesp = result.scalars().all()
            role_dict = {}
            for i in rolesp:
                outv = {}
                outv["score"] = max(i.score_bonus, 1)
                outv["kudos"] = max(i.kudos_bonus, 1)
                role_dict[i.role_id] = outv
            return role_dict

    @classmethod
    async def get_role_score_entry(cls, guild_id: int, role_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                and_(cls.guild_id == guild_id, cls.role_id == role_id)
            )
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def update_role_score_mod(
        cls, guild_id: int, role_id: int, score: float = 0, kudos: float = 0.0
    ):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(
                and_(cls.guild_id == guild_id, cls.role_id == role_id)
            )
            result = await session.execute(query)
            leaderboard_entry = result.scalar()

            if leaderboard_entry:

                leaderboard_entry.score_bonus = score
                if kudos > 0:
                    leaderboard_entry.kudos_bonus = kudos
                await session.commit()
                return leaderboard_entry
            else:
                leaderboard_entry = cls(
                    guild_id=guild_id,
                    role_id=role_id,
                    score_bonus=score,
                    kudos_bonus=kudos,
                )
                session.add(leaderboard_entry)
                await session.commit()
                return leaderboard_entry


async def setup(bot):
    DatabaseSingleton("mainsetup").load_base(Base)
