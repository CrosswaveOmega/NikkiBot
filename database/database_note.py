import json
from typing import Union
from sqlalchemy import (
    Column,
    Integer,
    Text,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Double,
    and_,
    delete,
    true,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from .database_singleton import DatabaseSingleton
from sqlalchemy import select, not_, func

"""Tables related to the AI stuff."""


from .database_main import AwareDateTime

from dateutil import rrule, tz

from datetime import datetime, time, timedelta
import utility.hash as hash

NoteBase = declarative_base(name="NoteTaking")

# Also for testing DatabaseSingleton's asyncronous mode.


class NotebookAux(NoteBase):
    __tablename__ = "notebase"

    user_id = Column(Integer, primary_key=True)
    entry_id = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    topic = Column(String, nullable=True)
    date = Column(AwareDateTime)

    @staticmethod
    async def add(user_id: int, entry_id: str, key: str, topic: str, date: datetime):
        async with await DatabaseSingleton.get_async_session() as session:
            # Check if the entry already exists
            existing_entry = await session.execute(
                select(NotebookAux).where(
                    NotebookAux.user_id == user_id,
                    NotebookAux.entry_id == entry_id,
                )
            )
            existing_entry = existing_entry.scalars().first()

            if existing_entry:
                existing_entry.date = date
            else:
                new_timer = NotebookAux(
                    user_id=user_id, entry_id=entry_id, key=key, topic=topic, date=date
                )
                session.add(new_timer)

            await session.commit()
            return existing_entry if existing_entry else new_timer

    @staticmethod
    async def list_topic(user_id):
        async with await DatabaseSingleton.get_async_session() as session:
            topics = await session.execute(
                select(NotebookAux.topic, func.count(NotebookAux.topic))
                .where(NotebookAux.user_id == user_id)
                .group_by(NotebookAux.topic)
            )
            return topics.fetchall()

    @staticmethod
    async def list_keys(user_id):
        async with await DatabaseSingleton.get_async_session() as session:
            topic_key_pairs = await session.execute(
                select(NotebookAux.topic, NotebookAux.key).where(
                    NotebookAux.user_id == user_id
                )
            )
            topic_key_pairs = topic_key_pairs.fetchall()
            print(topic_key_pairs)
            grouped_by_topic = {}
            for topic, key in topic_key_pairs:
                if topic not in grouped_by_topic:
                    grouped_by_topic[topic] = []
                grouped_by_topic[topic].append(key)
            return grouped_by_topic

    @staticmethod
    async def get_ids(user_id, key: str = None, topic: str = None, offset: int = 0):
        async with await DatabaseSingleton.get_async_session() as session:
            topics = await session.execute(
                select(NotebookAux.entry_id)
                .where(
                    and_(
                        NotebookAux.user_id == user_id,
                        NotebookAux.key == key if key is not None else true(),
                        NotebookAux.topic == topic if topic is not None else true(),
                    )
                )
                .order_by(NotebookAux.date)
                .offset(offset)
                .limit(128)
            )
            return topics.scalars().all()

    @staticmethod
    async def count_notes(user_id, key: str = None, topic: str = None, offset: int = 0):
        async with await DatabaseSingleton.get_async_session() as session:
            note_count = await session.execute(
                select(func.count(NotebookAux.entry_id))
                .where(
                    and_(
                        NotebookAux.user_id == user_id,
                        NotebookAux.key == key if key is not None else true(),
                        NotebookAux.topic == topic if topic is not None else true(),
                    )
                )
            )
            return note_count.scalar()

    @staticmethod
    async def remove(user_id: int, key: str = None, topic: str = None):
        async with await DatabaseSingleton.get_async_session() as session:
            await session.execute(
                delete(NotebookAux).where(
                    and_(
                        NotebookAux.user_id == user_id,
                        NotebookAux.key == key if key is not None else true(),
                        NotebookAux.topic == topic if topic is not None else true(),
                    )
                )
            )
            await session.commit()

    def __str__(self):
        return f"Timer: **{self.name}**, in <t:{int(self.invoke_on.timestamp())}:R>, on {self.message_url}"


DatabaseSingleton("mainsetup").load_base(NotebookAux)
