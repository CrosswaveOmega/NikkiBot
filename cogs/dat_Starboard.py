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


class StarboardEmojis(Base):
    __tablename__ = "starboard_emojis"

    guild_id = Column(BigInteger, primary_key=True)
    emoji = Column(String, primary_key=True)

    @classmethod
    async def add_emoji(cls, starboard_id: int, emoji: str):
        async with DatabaseSingleton.get_async_session() as session:
            new_emoji = cls(guild_id=starboard_id, emoji=emoji)
            session.add(new_emoji)
            await session.commit()
            return new_emoji

    @classmethod
    async def get_emoji(cls, starboard_id: int, emoji: str):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == starboard_id, cls.emoji == emoji)
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def remove_emoji(cls, starboard_id: int, emoji: str):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == starboard_id, cls.emoji == emoji)
            result = await session.execute(query)
            emoji_entry = result.scalar()
            if emoji_entry:
                await session.delete(emoji_entry)
                await session.commit()
                return True
            return False

    @classmethod
    async def get_emojis(cls, starboard_id: int, limit: int = 25):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == starboard_id).limit(limit)
            result = await session.execute(query)
            emojis = result.scalars().all()
            return [s.emoji for s in emojis]


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

        print("entry being updated or added", entry, message_id, guild_id, message_url)
        if entry:
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
    async def list_starrer_emojis(cls, guild_id: int, message_id: int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls.emoji).where(
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


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tagname = Column(String, unique=True, nullable=False)
    tag_category = Column(String, nullable=True, default="Uncategorized")
    user = Column(Integer, nullable=False)
    guildid = Column(Integer, nullable=True)
    guild_only = Column(Boolean, nullable=True, default=False)
    text = Column(String, nullable=False)
    image = Column(LargeBinary, nullable=True, default=None)
    imfilename = Column(String, nullable=True)
    lastupdate = Column(AwareDateTime, nullable=False)
    taguses = Column(Integer, nullable=True, default=0)

    @classmethod
    @ensure_session
    async def add(
        cls,
        tagname: str,
        user: int,
        text: str,
        lastupdate: datetime,
        guildid: int,
        guildonly: bool = False,
        tag_category: str = "Uncategorized",
        imb=None,
        imname: str = None,
        session: OptionalSession = None,
    ):
        statement = select(cls).where(cls.tagname == tagname)
        existing_tag = await session.execute(statement)
        existing_tag = existing_tag.scalars().first()

        if existing_tag:
            if existing_tag.user != user:
                return None
            existing_tag.text = text
            existing_tag.lastupdate = lastupdate
        else:
            new_tag = cls(
                tagname=tagname,
                user=user,
                text=text,
                lastupdate=lastupdate,
                guildid=guildid,
                guild_only=guildonly,
                tag_category=tag_category,
                image=imb,
                imfilename=imname,
            )
            session.add(new_tag)

        await session.commit()
        return existing_tag if existing_tag else new_tag

    @staticmethod
    async def delete(tagname: str, user: int):
        async with DatabaseSingleton.get_async_session() as session:
            tag = await session.execute(select(Tag).where(Tag.tagname == tagname))
            tag = tag.scalars().first()
            if tag and tag.user == user:
                await session.delete(tag)
                await session.commit()
                return tag
            return None

    @staticmethod
    async def delete_without_user(tagname: str):
        async with DatabaseSingleton.get_async_session() as session:
            tag = await session.execute(select(Tag).where(Tag.tagname == tagname))
            tag = tag.scalars().first()
            if tag:
                await session.delete(tag)
                await session.commit()
                return tag
            return None

    @staticmethod
    async def edit(
        tagname: str,
        user: int,
        newtext: Optional[str] = None,
        guild_only: Optional[bool] = None,
        imb: Optional[ByteString] = None,
    ):
        async with DatabaseSingleton.get_async_session() as session:
            tagq = await session.execute(select(Tag).where(Tag.tagname == tagname))
            tag = tagq.scalars().first()
            if tag and tag.user == user:
                if newtext != None:
                    tag.text = newtext
                if guild_only is not None:
                    tag.guild_only = guild_only
                tag.lastupdate = discord.utils.utcnow()
                if imb != None:
                    tag.image = imb
                await session.commit()
                return tag
            return None

    @classmethod
    @ensure_session
    async def get(
        cls,
        tagname: str,
        guildid: Optional[int] = None,
        session: OptionalSession = None,
    ):
        statement_a = select(cls).where(
            and_(
                cls.tagname == tagname,
                or_(cls.guild_only == False, cls.guildid == guildid),
            )
        )
        if guildid == None:
            statement_a = select(cls).where(cls.tagname == tagname)
        tag = await session.execute(statement_a)
        return tag.scalars().first()

    @classmethod
    @ensure_session
    async def increment(
        cls,
        tagname: str,
        guildid: Optional[int] = None,
        session: OptionalSession = None,
    ):
        statement_a = select(cls).where(
            and_(
                cls.tagname == tagname,
                or_(cls.guild_only == False, cls.guildid == guildid),
            )
        )
        if guildid == None:
            statement_a = select(cls).where(cls.tagname == tagname)
        tag = await session.execute(statement_a)
        tag = tag.scalars().first()
        if tag:
            if tag.taguses == None:
                tag.taguses = 0
            tag.taguses += 1
            await session.commit()
            return True
        return False

    @classmethod
    @ensure_session
    async def get_matching_tags(
        cls, tagname: str, gid: int, session: OptionalSession = None
    ):

        tag = await session.execute(
            select(cls)
            .where(
                and_(
                    cls.tagname.like(f"%{tagname}%"),
                    or_(cls.guild_only == False, cls.guildid == gid),
                )
            )
            .limit(25)
        )
        return tag.scalars().all()

    @staticmethod
    async def list_all(gid: int):
        async with DatabaseSingleton.get_async_session() as session:
            tags = await session.execute(
                select(Tag.tagname).where(
                    or_(Tag.guild_only == False, Tag.guildid == gid)
                )
            )
            return tags.scalars().all()

    @staticmethod
    async def list_all_cat(gid: int):
        async with DatabaseSingleton.get_async_session() as session:
            tags = await session.execute(
                select(Tag.tag_category, Tag.tagname, Tag.text).where(
                    or_(Tag.guild_only == False, Tag.guildid == gid)
                )
            )
            tag_dict = {}
            for tag_category, tagname, text in tags:
                if tag_category not in tag_dict:
                    tag_dict[tag_category] = []
                tag_dict[tag_category].append((tagname, text))
            return tag_dict

    @classmethod
    @ensure_session
    async def does_tag_exist(cls, tagname, session: OptionalSession = None):
        statement = select(cls).where(cls.tagname == tagname)
        existing_tag = await session.execute(statement)
        existing_tag = existing_tag.scalars().first()
        if existing_tag:
            return True
        return False

    def get_dict(self):
        tag = {
            "tagname": self.tagname,
            "topic": self.tag_category,
            "user": self.user,
            "text": self.text,
            "lastupdate": self.lastupdate,
            "filename": self.imfilename,
            "guild_only": self.guild_only,
            "uses": self.taguses,
        }
        return tag
    

class TempVCConfig(Base):
    __tablename__ = "temp_vc_config"

    guild_id = Column(BigInteger, primary_key=True)  # Using guild_id as the primary key
    category_id = Column(BigInteger, nullable=False)  # Storing the target category ID

    max_users = Column(Integer, nullable=False, default=10)
    max_channels = Column(Integer, nullable=False, default=5)

    @classmethod
    async def get_temp_vc_config(cls, guild_id: int):
        """Fetches the configuration for a specific guild."""
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            return result.scalar()

    @classmethod
    async def add_temp_vc_config(cls, guild_id: int, category_id: int, max_users:int=10,max_channels:int=5):
        """Adds a new configuration entry for the guild."""
        async with DatabaseSingleton.get_async_session() as session:
            config = cls(guild_id=guild_id, category_id=category_id, max_users=max_users, max_channels=max_channels)
            session.add(config)
            await session.commit()
            return config

    @classmethod
    async def remove_temp_vc_config(cls, guild_id: int):
        """Removes the configuration entry for the guild."""
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            config = result.scalar()
            if config:
                await session.delete(config)
                await session.commit()
                return True
            return False

    @classmethod
    async def update_category(cls, guild_id: int, new_category_id: int):
        """Updates the category ID for the guild's temporary VC configuration."""
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            config = result.scalar()
            if config:
                config.category_id = new_category_id
                await session.commit()
                return config
            return None

    @classmethod
    async def update_max_users(cls, guild_id: int, new_max_users: int):
        """Updates the max users for the guild's temporary VC configuration."""
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            config = result.scalar()
            if config:
                config.max_users = new_max_users
                await session.commit()
                return config
            return None

    @classmethod
    async def update_max_channels(cls, guild_id: int, new_max_channels: int):
        """Updates the max channels for the guild's temporary VC configuration."""
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            config = result.scalar()
            if config:
                config.max_channels = new_max_channels
                await session.commit()
                return config
            return None
        
    @classmethod
    async def delete(cls, guild_id:int):
        async with DatabaseSingleton.get_async_session() as session:
            query = select(cls).where(cls.guild_id == guild_id)
            result = await session.execute(query)
            value = query.scalars().first()
            if value:
                await session.delete(value)
                await session.commit()
                return True
            return False
        
        


        
        
async def setup(bot):
    DatabaseSingleton("mainsetup").load_base(Base)
