import traceback
from utility import filter_trace_stack
from sqlalchemy import types
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
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from .database_singleton import DatabaseSingleton
from sqlalchemy import select, not_, func
import datetime

"""This defines a few universal tables."""
"""As well as a function for the singleton to collect the base it's defined within."""


class AwareDateTime(types.TypeDecorator):
    impl = types.DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            # print("ADD",value)
            # Convert the datetime to UTC if it's aware
            if value.utcoffset() is not None:
                # print("ADD",self,value,value.tzinfo)
                # form=traceback.format_stack()
                # print(form)
                # out=filter_trace_stack(form)
                # print(out)

                value = value.astimezone(datetime.timezone.utc)
        # print("result",value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            # print("add",value)
            # Convert the datetime to local timezone if it's naive
            if value.utcoffset() is None:
                value = value.replace(tzinfo=datetime.timezone.utc).astimezone()
        # print("result",value)
        return value


Main_DB_Base = declarative_base(name="Main DB Base")


class ServerData(Main_DB_Base):
    """
    Server Data is used as a global table for guilds the bot is in.
    All joined guilds will will have an entry here.
    It keeps track of the last time any guild used a command or service,
    so old data can be wiped for the sake of privacy.
    """

    __tablename__ = "ServerData"
    server_id = Column(Integer, primary_key=True, nullable=False, unique=True)

    last_use = Column(AwareDateTime)
    """the last time a guild used any command."""

    # my_channel=Column(Integer, nullable=True)
    # '''the bot's personal fallback channel.'''

    policy_agree = Column(Boolean, default=False)
    """
    Server has read and acknowledged the terms of service and privacy policy before use.
    """

    @classmethod
    def get(cls, server_id):
        """
        Returns the entire ServerArchiveProfile entry for the specified server_id, or None if it doesn't exist.
        """
        session: Session = DatabaseSingleton.get_session()
        result = session.query(ServerData).filter_by(server_id=server_id).first()
        if result:
            return result
        else:
            return None

    @staticmethod
    def get_or_new(server_id):
        new = ServerData.get(server_id)
        if not new:
            session = DatabaseSingleton.get_session()
            new = ServerData(server_id=server_id)
            session.add(new)
            session.commit()
        return new

    @classmethod
    def Audit(cls, list_of_servers):
        """
        Returns all entries in ServerData with a last_use value older than 30 days,
        and a server_id that is not in the passed-in list.
        """
        session = DatabaseSingleton.get_session()
        threshold = datetime.datetime.now() - datetime.timedelta(days=30)

        results = (
            session.query(ServerData)
            .filter(
                ServerData.last_use < threshold,
                not_(ServerData.server_id.in_(list_of_servers)),
            )
            .all()
        )
        return results

    def update(self, **kwargs):
        session = DatabaseSingleton.get_session()
        for key, value in kwargs.items():
            setattr(self, key, value)

    def update_last_time(self):
        self.last_use = datetime.datetime.now()


class ServerArchiveProfile(Main_DB_Base):
    """utility for the server archive system."""

    __tablename__ = "ServerArchiveProfiles"

    server_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    servername = Column(Text)
    last_archive_time = Column(AwareDateTime)
    history_channel_id = Column(Integer)

    average_message_archive_time = Column(Double, default=2.5)

    average_sep_archive_time = Column(Double, default=3.0)

    last_group_num = Column(Integer, default=0)
    status = Column(Text)
    archive_scope = Column(Text, default="ws")
    archive_dynamic = Column(Boolean, default=False)

    channellist = relationship(
        "IgnoredChannel", back_populates="server_archive_profile"
    )
    ignoredauthors = relationship(
        "IgnoredUser", back_populates="server_archive_profile"
    )

    def to_dict(self):
        profile_dict = {}
        for column in self.__table__.columns:
            profile_dict[column.name] = getattr(self, column.name)
        return profile_dict

    @classmethod
    def get(cls, server_id):
        """
        Returns the entire ServerArchiveProfile entry for the specified server_id, or None if it doesn't exist.
        """
        session: Session = DatabaseSingleton.get_session()
        result = (
            session.query(ServerArchiveProfile).filter_by(server_id=server_id).first()
        )
        if result:
            return result
        else:
            return None

    @staticmethod
    def get_or_new(server_id):
        new = ServerArchiveProfile.get(server_id)
        if not new:
            session = DatabaseSingleton.get_session()
            new = ServerArchiveProfile(server_id=server_id)
            session.add(new)
            session.commit()
        return new

    @staticmethod
    def get_entry(server_id: int):
        session = DatabaseSingleton.get_session()
        result = (
            session.query(ServerArchiveProfile).filter_by(server_id=server_id).first()
        )
        if result:
            return {
                column.name: getattr(result, column.name)
                for column in result.__table__.columns
            }
        else:
            return None

    @staticmethod
    def add_or_update(server_id, **kwargs):
        session: Session = DatabaseSingleton.get_session()
        profile = (
            session.query(ServerArchiveProfile).filter_by(server_id=server_id).first()
        )
        if not profile:
            profile = ServerArchiveProfile(server_id=server_id)
            session.add(profile)
        for key, value in kwargs.items():
            setattr(profile, key, value)
        session.commit()

    def update(self, **kwargs):
        session = DatabaseSingleton.get_session()
        for key, value in kwargs.items():
            setattr(self, key, value)
        # session.add(self)
        session.commit()

    def get_columns_by_name(self, *column_names):
        result = {}
        for name in column_names:
            result[name] = getattr(self, name, None)
        return result

    def add_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = (
            session.query(IgnoredChannel)
            .filter_by(server_profile_id=self.server_id, channel_id=channel_id)
            .first()
        )
        if not channel:
            channel = IgnoredChannel(
                server_profile_id=self.server_id, channel_id=channel_id
            )
            session.add(channel)
            session.commit()
            return True
        return False

    def remove_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = (
            session.query(IgnoredChannel)
            .filter_by(server_profile_id=self.server_id, channel_id=channel_id)
            .first()
        )
        if channel:
            session.delete(channel)
            session.commit()
            return True
        return False

    def has_channel(self, channel_id):
        """make sure this channel is not in the ignore list, or is the history channel."""
        if self.history_channel_id == channel_id:
            return True
        session = DatabaseSingleton.get_session()
        channel = (
            session.query(IgnoredChannel)
            .filter_by(server_profile_id=self.server_id, channel_id=channel_id)
            .first()
        )
        return channel is not None

    def add_user(self, user_id):
        session = DatabaseSingleton.get_session()
        user = (
            session.query(IgnoredUser)
            .filter_by(server_profile_id=self.server_id, user_id=user_id)
            .first()
        )
        if not user:
            user = IgnoredUser(server_profile_id=self.server_id, user_id=user_id)
            session.add(user)
            session.commit()
            return True
        return False

    def remove_user(self, user_id):
        session = DatabaseSingleton.get_session()
        user = (
            session.query(IgnoredUser)
            .filter_by(server_profile_id=self.server_id, user_id=user_id)
            .first()
        )
        if user:
            session.delete(user)
            session.commit()
            return True
        return False

    def has_user(self, user_id):
        session = DatabaseSingleton.get_session()
        user = (
            session.query(IgnoredUser)
            .filter_by(server_profile_id=self.server_id, user_id=user_id)
            .first()
        )
        return user is not None

    def list_channels(self):
        session = DatabaseSingleton.get_session()
        ignoredchannels = (
            session.query(IgnoredChannel)
            .filter_by(server_profile_id=self.server_id)
            .all()
        )
        return [channel.channel_id for channel in ignoredchannels]

    def count_channels(self):
        session = DatabaseSingleton.get_session()
        count = (
            session.query(func.count(IgnoredChannel.channel_id))
            .filter_by(server_profile_id=self.server_id)
            .scalar()
        )
        return count

    def list_users(self):
        session = DatabaseSingleton.get_session()
        ignoredusers = (
            session.query(IgnoredUser).filter_by(server_profile_id=self.server_id).all()
        )
        return [user.user_id for user in ignoredusers]

    def get_details(self):
        scopes = {
            "ws": "Bots and Webhooks Only",
            "user": "User Messages Only",
            "both": "Will archive everything.",
        }
        string = f"**Archive Scope:**{scopes.get(self.archive_scope)}\n**Active Collect:**{self.archive_dynamic}"
        return string

    def __repr__(self):
        session = DatabaseSingleton.get_session()
        result = (
            session.query(ServerArchiveProfile)
            .filter_by(server_id=self.server_id)
            .first()
        )
        if result:
            return str(
                {
                    column.name: getattr(result, column.name)
                    for column in result.__table__.columns
                }
            )
        else:
            return None


class IgnoredChannel(Main_DB_Base):
    __tablename__ = "ignoredchannels"

    id = Column(Integer, primary_key=True)
    server_profile_id = Column(Integer, ForeignKey("ServerArchiveProfiles.server_id"))
    channel_id = Column(Integer)
    server_archive_profile = relationship(
        "ServerArchiveProfile", back_populates="channellist"
    )


class IgnoredUser(Main_DB_Base):
    __tablename__ = "ignoredusers"

    id = Column(Integer, primary_key=True)
    server_profile_id = Column(Integer, ForeignKey("ServerArchiveProfiles.server_id"))
    user_id = Column(Integer)
    server_archive_profile = relationship(
        "ServerArchiveProfile", back_populates="ignoredauthors"
    )


class Users_DoNotTrack(Main_DB_Base):
    __tablename__ = "dntusers"
    user_id = Column(Integer, primary_key=True)
    reason = Column(Text, default="self")

    @staticmethod
    def check_entry(user_id: int) -> bool:
        session = DatabaseSingleton.get_session()
        entry = (
            session.query(Users_DoNotTrack)
            .filter(Users_DoNotTrack.user_id == user_id)
            .first()
        )
        return entry is not None

    @staticmethod
    def add_entry(user_id: int, reason: str) -> None:
        session = DatabaseSingleton.get_session()
        entry = Users_DoNotTrack(user_id=user_id, reason=reason)
        session.add(entry)
        session.commit()

    @staticmethod
    def delete_entry(user_id: int, reason: str) -> bool:
        session = DatabaseSingleton.get_session()
        entry = (
            session.query(Users_DoNotTrack)
            .filter(
                Users_DoNotTrack.user_id == user_id, Users_DoNotTrack.reason == reason
            )
            .first()
        )

        if entry:
            session.delete(entry)
            session.commit()
            return True
        else:
            return False


DatabaseSingleton("mainsetup").load_base(Main_DB_Base)
