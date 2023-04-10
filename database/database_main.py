from typing import Union
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, Double
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from .database_singleton import DatabaseSingleton
from sqlalchemy import select

'''This defines a few universal tables.'''
'''As well as a function for the singleton to collect the base it's defined within.'''


Base = declarative_base()
class ServerArchiveProfile(Base):
    __tablename__ = "ServerArchiveProfiles"

    server_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    servername = Column(Text)
    last_archive_time = Column(DateTime)
    history_channel_id = Column(Integer)
    last_group_num= Column(Integer, default=0)
    status = Column(Text)

    channellist = relationship("IgnoredChannel", back_populates="server_archive_profile")
    ignoredauthors = relationship("IgnoredUser", back_populates="server_archive_profile")

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
        session:Session = DatabaseSingleton.get_session()
        result = session.query(ServerArchiveProfile).filter_by(server_id=server_id).first()
        if result:            return result
        else:            return None
    
    @staticmethod
    def get_or_new(server_id):
        new=ServerArchiveProfile.get(server_id)
        if not new:
            session=DatabaseSingleton.get_session()
            new = ServerArchiveProfile(server_id=server_id)
            session.add(new)
            session.commit()
        return new
        
    @staticmethod
    def get_entry(server_id: int):
        session = DatabaseSingleton.get_session()
        result = session.query(ServerArchiveProfile).filter_by(server_id=server_id).first()
        if result:  return {column.name: getattr(result, column.name) for column in result.__table__.columns}
        else: return None


    @staticmethod
    def add_or_update(server_id, **kwargs):
        session:Session=DatabaseSingleton.get_session()
        profile = session.query(ServerArchiveProfile).filter_by(server_id=server_id).first()
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
        #session.add(self)
        session.commit()

    def get_columns_by_name(self, *column_names):
        result = {}
        for name in column_names:
            result[name] = getattr(self, name, None)
        return result

    def add_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = session.query(IgnoredChannel).filter_by(server_profile_id=self.server_id, channel_id=channel_id).first()
        if not channel:
            channel = IgnoredChannel(server_profile_id=self.server_id, channel_id=channel_id)
            session.add(channel)
            session.commit()
            return True
        return False

    def remove_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = session.query(IgnoredChannel).filter_by(server_profile_id=self.server_id, channel_id=channel_id).first()
        if channel:
            session.delete(channel)
            session.commit()
            return True
        return False

    def has_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = session.query(IgnoredChannel).filter_by(server_profile_id=self.server_id, channel_id=channel_id).first()
        return channel is not None

    def add_user(self, user_id):
        session = DatabaseSingleton.get_session()
        user = session.query(IgnoredUser).filter_by(server_profile_id=self.server_id, user_id=user_id).first()
        if not user:
            user = IgnoredUser(server_profile_id=self.server_id, user_id=user_id)
            session.add(user)
            session.commit()
            return True
        return False

    def remove_user(self, user_id):
        session = DatabaseSingleton.get_session()
        user = session.query(IgnoredUser).filter_by(server_profile_id=self.server_id, user_id=user_id).first()
        if user:
            session.delete(user)
            session.commit()
            return True
        return False

    def has_user(self, user_id):
        session = DatabaseSingleton.get_session()
        user = session.query(IgnoredUser).filter_by(server_profile_id=self.server_id, user_id=user_id).first()
        return user is not None

    def list_channels(self):
        session = DatabaseSingleton.get_session()
        ignoredchannels = session.query(IgnoredChannel).filter_by(server_profile_id=self.server_id).all()
        return [channel.channel_id for channel in ignoredchannels]

    def list_users(self):
        session = DatabaseSingleton.get_session()
        ignoredusers = session.query(IgnoredUser).filter_by(server_profile_id=self.server_id).all()
        return [user.user_id for user in ignoredusers]
    def __repr__(self):
        session = DatabaseSingleton.get_session()
        result = session.query(ServerArchiveProfile).filter_by(server_id=self.server_id).first()
        if result:
            return str({column.name: getattr(result, column.name) for column in result.__table__.columns})
        else:
            return None

    

        
    
    

class IgnoredChannel(Base):
    __tablename__ = "ignoredchannels"

    id = Column(Integer, primary_key=True)
    server_profile_id = Column(Integer, ForeignKey("ServerArchiveProfiles.server_id"))
    channel_id = Column(Integer)
    server_archive_profile  = relationship("ServerArchiveProfile", back_populates="channellist")

class IgnoredUser(Base):
    __tablename__ = "ignoredusers"

    id = Column(Integer, primary_key=True)
    server_profile_id = Column(Integer, ForeignKey("ServerArchiveProfiles.server_id"))
    user_id = Column(Integer)
    server_archive_profile  = relationship("ServerArchiveProfile", back_populates="ignoredauthors")



def return_base():
    return Base