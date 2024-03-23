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
    entry_id= Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    topic = Column(String, nullable=True)
    date = Column(AwareDateTime)

    @staticmethod
    async def add(user_id:int, entry_id:str, key:str,topic:str,date:datetime):
        async with await DatabaseSingleton.get_async_session() as session:
            new_timer = NotebookAux(
                user_id=user_id, entry_id=entry_id, key=key,topic=topic,date=date
            )
            session.add(new_timer)
            await session.commit()
            return new_timer

    @staticmethod
    async def list_topic(user_id):
        async with await DatabaseSingleton.get_async_session() as session:
            topics = await session.execute(
                select(NotebookAux.topic, func.count(NotebookAux.topic)).where(NotebookAux.user_id == user_id).group_by(NotebookAux.topic)
            )
            return topics.fetchall()
    @staticmethod
    async def remove(user_id:int, key:str=None,topic:str=None):
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
