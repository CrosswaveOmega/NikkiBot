import json
from sqlalchemy import (
    Column,
    Integer,
    Text,
    String,
    Boolean,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from .database_singleton import DatabaseSingleton

"""Tables related to the AI stuff."""


from .database_main import AwareDateTime

from dateutil import rrule

from datetime import datetime
import utility.hash as hash

AIBase = declarative_base(name="AI Feature Base")


class AuditProfile(AIBase):
    """This table manages per server/user rate limits for any gpt API.
    It is not audited to preserve any needed bans.
    """

    __tablename__ = "audit_profile"

    id = Column(String, primary_key=True)
    type = Column(String, primary_key=True)
    processing = Column(Boolean, default=False)
    DailyLimit = Column(Integer, default=20)
    banned = Column(Boolean, default=False)
    banned_since = Column(DateTime, nullable=True)
    ban_reason = Column(Text, default="")
    current = Column(Integer, default=0)
    last_call = Column(DateTime, nullable=True)
    started_dt = Column(DateTime, nullable=True)
    disabled = Column(Boolean, nullable=True, default=False)

    def set_rollover(self):
        """Change the internal rollover time."""
        rule = rrule.rrule(
            rrule.DAILY,
            dtstart=datetime.now().replace(hour=18, minute=0, second=0, microsecond=0),
            byhour=18,
            byminute=0,
            bysecond=0,
        )
        self.started_dt = rule.after(datetime.now())

    def checktime(self):
        if self.started_dt == None:
            self.set_rollover()
        if self.last_call != None:
            if self.last_call > self.started_dt:
                self.current = 0
                self.set_rollover()
        elif self.last_call == None:
            self.last_call = datetime.fromtimestamp(0)
            self.set_rollover()

    @staticmethod
    def get_or_new(server, user):
        sa = AuditProfile.get_server(server.id)
        ua = AuditProfile.get_user(user.id)
        if sa == None:
            sa = AuditProfile.add(server.id, "server")
        if ua == None:
            ua = AuditProfile.add(user.id, "user", True)
        return sa, ua

    @classmethod
    def get_server(cls, server_id):
        targetid, num = hash.hash_string(
            str(server_id), hashlen=16, hashset=hash.Hashsets.base64
        )
        session = DatabaseSingleton.get_session()
        result = (
            session.query(cls).filter(cls.type == "server", cls.id == targetid).first()
        )
        if result:
            return result
        else:
            return None

    @classmethod
    def get_user(cls, user_id):
        targetid, num = hash.hash_string(
            str(user_id), hashlen=16, hashset=hash.Hashsets.base64
        )
        session = DatabaseSingleton.get_session()
        result = (
            session.query(cls).filter(cls.type == "user", cls.id == targetid).first()
        )
        if result:
            return result
        else:
            return None

    @classmethod
    def add(cls, id, type, disabled=False):
        targetid, num = hash.hash_string(
            str(id), hashlen=16, hashset=hash.Hashsets.base64
        )
        session = DatabaseSingleton.get_session()
        entry = cls(id=targetid, type=type, disabled=disabled)
        if type == "server":
            entry.DailyLimit = 50
        session.add(entry)
        session.commit()
        return entry

    def check_if_ok(self):
        if self.current > self.DailyLimit:
            return False, "messagelimit"
        if self.banned:
            return False, "ban"
        if self.last_call is not None:
            if (datetime.now() - self.last_call).total_seconds() < 15:
                return False, "cooldown"
        if self.disabled:
            return False, "disable"
        return True, "ok"

    def modify_status(self):
        self.current += 1
        self.last_call = datetime.now()

    def ban(self):
        self.banned = True
        self.banned_since = datetime.now()

    def unban(self):
        self.banned = False
        self.banned_since = None


class ServerAIConfig(AIBase):
    __tablename__ = "ServerAIConfig"

    server_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    restrict = Column(Boolean, nullable=True, default=True)

    enabled_channels = relationship("EnabledChannel", back_populates="server_ai_config")
    message_chains = relationship("MessageChain", back_populates="server_ai_config")

    @classmethod
    def get(cls, server_id):
        session = DatabaseSingleton.get_session()
        return session.query(cls).filter_by(server_id=server_id).first()

    @staticmethod
    def get_or_new(server_id):
        session = DatabaseSingleton.get_session()
        config = session.query(ServerAIConfig).filter_by(server_id=server_id).first()
        if not config:
            config = ServerAIConfig(server_id=server_id)
            session.add(config)
            session.commit()
        return config

    @staticmethod
    def add_or_update(server_id, **kwargs):
        session = DatabaseSingleton.get_session()
        config = session.query(ServerAIConfig).filter_by(server_id=server_id).first()
        if not config:
            config = ServerAIConfig(server_id=server_id)
            session.add(config)
        for key, value in kwargs.items():
            setattr(config, key, value)
        session.commit()

    def add_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = (
            session.query(EnabledChannel)
            .filter_by(server_id=self.server_id, channel_id=channel_id)
            .first()
        )
        if not channel:
            channel = EnabledChannel(server_id=self.server_id, channel_id=channel_id)
            session.add(channel)
            session.commit()
            return True
        return False

    def remove_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = (
            session.query(EnabledChannel)
            .filter_by(server_id=self.server_id, channel_id=channel_id)
            .first()
        )
        if channel:
            session.delete(channel)
            session.commit()
            return True
        return False

    def has_channel(self, channel_id):
        session = DatabaseSingleton.get_session()
        channel = (
            session.query(EnabledChannel)
            .filter_by(server_id=self.server_id, channel_id=channel_id)
            .first()
        )
        return channel is not None

    def list_channels(self):
        session = DatabaseSingleton.get_session()
        enabled_channels = (
            session.query(EnabledChannel).filter_by(server_id=self.server_id).all()
        )
        return [channel.channel_id for channel in enabled_channels]

    def count_channels(self):
        session = DatabaseSingleton.get_session()
        count = (
            session.query(EnabledChannel).filter_by(server_id=self.server_id).count()
        )
        return count

    def add_message_to_chain(
        self,
        message_id,
        created_at,
        thread_id=None,
        role=None,
        content=None,
        name=None,
        function=None,
    ):
        session = DatabaseSingleton.get_session()
        message_chain = MessageChain(
            server_id=self.server_id,
            message_id=message_id,
            thread_id=thread_id,
            created_at=created_at,
            role=role,
            content=content,
            name=name,
            function=json.dumps(function),
        )
        session.add(message_chain)
        session.commit()

    def remove_message_chain(self, message_id):
        session = DatabaseSingleton.get_session()
        message_chain = (
            session.query(MessageChain)
            .filter_by(server_id=self.server_id, message_id=message_id)
            .first()
        )
        if message_chain:
            session.delete(message_chain)
            session.commit()

    def list_message_chains(self, thread_id=None):
        session = DatabaseSingleton.get_session()
        if thread_id:
            message_chains = (
                session.query(MessageChain)
                .filter_by(server_id=self.server_id, thread_id=thread_id)
                .order_by(MessageChain.created_at)
                .limit(10)
                .all()
            )
            return message_chains
        message_chains = (
            session.query(MessageChain)
            .filter_by(server_id=self.server_id, thread_id=None)
            .order_by(MessageChain.created_at)
            .limit(10)
            .all()
        )
        return message_chains

    def prune_message_chains(self, limit=15, thread_id=None):
        session = DatabaseSingleton.get_session()
        message_chains = (
            session.query(MessageChain)
            .filter_by(server_id=self.server_id, thread_id=thread_id)
            .order_by(MessageChain.created_at.desc())
            .all()
        )
        if len(message_chains) > limit:
            message_chains_to_remove = message_chains[limit:]
            for message_chain in message_chains_to_remove:
                session.delete(message_chain)
            session.commit()
            session.flush()

    def clear_message_chains(self, thread_id=None):
        session = DatabaseSingleton.get_session()
        message_chains = (
            session.query(MessageChain)
            .filter_by(server_id=self.server_id, thread_id=thread_id)
            .all()
        )
        purged = 0
        for message_chain in message_chains:
            purged += 1
            session.delete(message_chain)
        session.commit()
        session.flush()
        return purged


class EnabledChannel(AIBase):
    __tablename__ = "EnabledChannel"

    id = Column(Integer, primary_key=True)
    server_id = Column(Integer, ForeignKey("ServerAIConfig.server_id"))
    channel_id = Column(Integer)

    server_ai_config = relationship("ServerAIConfig", back_populates="enabled_channels")


class MessageChain(AIBase):
    __tablename__ = "MessageChain"

    id = Column(Integer, primary_key=True)
    server_id = Column(Integer, ForeignKey("ServerAIConfig.server_id"))
    thread_id = Column(Integer, default=None)
    message_id = Column(Integer)
    created_at = Column(AwareDateTime)
    role = Column(String)
    content = Column(String)
    name = Column(String)
    function = Column(String)

    server_ai_config = relationship("ServerAIConfig", back_populates="message_chains")

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "tool_calls": (
                json.loads(self.function) if self.function is not None else None
            ),
        }


DatabaseSingleton("mainsetup").load_base(AIBase)
