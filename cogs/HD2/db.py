from sqlalchemy import (
    Column,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session
from database import DatabaseSingleton

SuperEarthBase = declarative_base(name="HD API Base")

# Also for testing DatabaseSingleton's asyncronous mode.


class ServerHDProfile(SuperEarthBase):
    __tablename__ = "server_superearth_profile"
    server_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    overview_message_url = Column(String, nullable=True, default=None)
    update_channel = Column(Integer, nullable=True, default=None)
    last_global_briefing = Column(String, nullable=True, default=None)
    webhook_url = Column(String, nullable=True, default=None)

    @classmethod
    def get(cls, server_id):
        """
        Returns the entire ServerHDProfile entry for the specified server_id, or None if it doesn't exist.
        """
        session: Session = DatabaseSingleton.get_session()
        result = session.query(ServerHDProfile).filter_by(server_id=server_id).first()
        if result:
            return result
        else:
            return None

    @staticmethod
    def get_or_new(server_id):
        new = ServerHDProfile.get(server_id)
        if not new:
            session = DatabaseSingleton.get_session()
            new = ServerHDProfile(server_id=server_id)
            session.add(new)
            session.commit()
        return new

    @staticmethod
    def get_entries_with_overview_message_id():
        """
        Returns all entries in ServerHDProfile with a non-null overview_message_id.
        """
        session = DatabaseSingleton.get_session()
        return (
            session.query(ServerHDProfile)
            .filter(ServerHDProfile.overview_message_url.isnot(None))
            .all()
        )

    @staticmethod
    def get_entries_with_webhook():
        """
        Returns a list of all distinct webhook_url values
        """
        session = DatabaseSingleton.get_session()
        query = (
            session.query(ServerHDProfile.webhook_url)
            .filter(ServerHDProfile.webhook_url.isnot(None))
            .distinct()
            .all()
        )
        return [row.webhook_url for row in query]

    @staticmethod
    def set_all_matching_webhook_to_none(webhook_url):
        """
        Sets all matching webhook_url values to None
        """
        session = DatabaseSingleton.get_session()
        session.query(ServerHDProfile).filter_by(webhook_url=webhook_url).update(
            {ServerHDProfile.webhook_url: None}
        )
        session.commit()

    def update(self, **kwargs):
        session = DatabaseSingleton.get_session()
        for key, value in kwargs.items():
            setattr(self, key, value)
        session.commit()


DatabaseSingleton("mainsetup").load_base(SuperEarthBase)
