from datetime import timezone
import discord
import io

from typing import List, Union
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Boolean 
from sqlalchemy import LargeBinary, ForeignKey,PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session

from database import DatabaseSingleton, add_or_update_all
from sqlalchemy import select,event, exc

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc, asc, and_

'''

This script defines Tables that are used exclusively within the context of the ServerRPArchive Cog and it's
ArchiveSub subpackage.

'''


Base=declarative_base()
class ChannelSep(Base):
    __tablename__ = 'ChannelSeps'

    channel_sep_id = Column(Integer,primary_key=True)
    server_id = Column(Integer,primary_key=True, default=69)
    channel = Column(String)
    category = Column(String)
    thread = Column(String)

    all_ok=Column(Boolean, default=False)
    neighbor_count=Column(Integer, default=0)

    created_at = Column(DateTime)
    posted_url = Column(String, nullable=True, default=None)

    __table_args__ = (
        PrimaryKeyConstraint('channel_sep_id', 'server_id'),
    )

    def get_chan_sep(self):
        return f"{self.category}-{self.channel}-{self.thread}"
    @staticmethod
    def get_separators_without(server_id: int):
        filter = and_(
            ChannelSep.posted_url == None,
            ChannelSep.server_id == server_id
        )
        session = DatabaseSingleton.get_session()
        return session.query(ChannelSep).filter(filter).order_by(ChannelSep.channel_sep_id).all()
    @staticmethod
    def get_all_separators(server_id: int):
        filter =            ChannelSep.server_id == server_id
        session = DatabaseSingleton.get_session()
        return session.query(ChannelSep).filter(filter).order_by(ChannelSep.created_at).all()
    
    @classmethod
    def get(cls, channel_sep_id, server_id):
        """
        Returns the entire ServerArchiveProfile entry for the specified server_id, or None if it doesn't exist.
        """
        session:Session = DatabaseSingleton.get_session()
        result = session.query(ChannelSep).filter(channel_sep_id=channel_sep_id,server_id=server_id).first()
        if result:            return result
        else:            return None
    def update(self, **kwargs):
        session = DatabaseSingleton.get_session()
        for key, value in kwargs.items():
            setattr(self, key, value)
        #session.add(self)
        session.commit()
    def get_messages(self):
        session = DatabaseSingleton.get_session()
        return session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == self.server_id) &
            (ArchivedRPMessage.channel_sep_id==self.channel_sep_id)
        ).order_by(ArchivedRPMessage.created_at).all()
    def get_authors(self):
        '''get a list of authors.'''
        session = DatabaseSingleton.get_session()
        authors = session.query(ArchivedRPMessage.author).filter(
            (ArchivedRPMessage.server_id == self.server_id) &
            (ArchivedRPMessage.channel_sep_id==self.channel_sep_id)
        ).distinct().all()
        return [author[0] for author in authors]
    def get_neighbor(self, use_channel=True, next=True, with_url=True):
        """
        Returns the channel_sep_id of the nearest ChannelSep with the same channel attribute and a
        lower (if next=False) or higher (if next=True) channel_sep_id than the current.
        
        :param use_channel: If True, filters ChannelSep by channel attribute.
        :param next: If True, finds the next channel sep, else finds the previous one.
        """
        session = DatabaseSingleton.get_session()
        filters = [ChannelSep.server_id == self.server_id]
        order = desc(ChannelSep.channel_sep_id)
        if use_channel:filters.append(ChannelSep.channel == self.channel)
        if next:
            filters.append(and_(ChannelSep.channel_sep_id > self.channel_sep_id))
            order = asc(ChannelSep.channel_sep_id)
        else: filters.append(and_(ChannelSep.channel_sep_id < self.channel_sep_id))
        if with_url:
            filters.append(and_(ChannelSep.posted_url!=None))  
            result = session.query(ChannelSep.posted_url)\
                .filter(*filters)\
                .order_by(order)\
                .first()
            if result: return result[0]
        else:
            filters.append(and_(ChannelSep.posted_url!=None))  
            result = session.query(ChannelSep)\
                .filter(*filters)\
                .order_by(order)\
                .first()
            if result:  return result
        return None
    
    def create_embed(self):
        defaultstr="EOL⏹️" #For the Index/Channel Index
        defaultcstr="EOCL⏹️" #For the Index/Channel Index
        defaultclstr="FIRST" #For the Index/Channel Index
        cembed=discord.Embed(colour=discord.Colour(0x7289da))

        cembed.add_field(name="Category", value=self.category, inline=True)
        if self.thread!=None:
            cembed.add_field(name="ParentChannel", value=self.channel, inline=True)
            cembed.add_field(name="Thread", value=self.thread, inline=True)
            #categorytext+= "\n**Channel**"+current_channel.Parent.name
        else:
            cembed.add_field(name="Channel", value=self.channel, inline=True)
        cembed.timestamp= self.created_at
        utcdate=self.created_at.replace(tzinfo=timezone.utc);
        cembed.set_footer(text=utcdate.strftime("%m-%d-%Y, %I:%M %p"))
        charlist=self.get_authors()
        lastm="██████"
        nextm=defaultstr
        lastcm=defaultclstr
        nextcm=defaultcstr
        iN,iL=self.get_neighbor(False,True),self.get_neighbor(False,False)
        cN,cL=self.get_neighbor(True,True),self.get_neighbor(True,False)

        count=0
        if iN!=None:  nextm="[▼Next▼]({})".format(iN); count+=1
        if iL!=None: lastm="[▲Last▲]({})".format(iL); count+=1
        if cN!=None: nextcm="[Next▼]({})".format(cN); count+=1
        if cL!=None:  lastcm="[▲Last]({})".format(cL); count+=1
        if iN!=None and iL!=None and cN!=None and cL!=None:
            self.update(all_ok=True)
        cembed.description="{} {} ░░░░░░░░░░░░░░░ {} channel {}".format(lastm, nextm, lastcm, nextcm)
        actorstr=", ".join(["`{}`".format(x) for x in charlist])
        if actorstr:
            if(len(actorstr)>1024): actorstr=actorstr[0:1023]
            cembed.add_field(name="Actors", value=actorstr, inline=False)
        return cembed, count
    def __repr__(self):
        return f"{self.channel_sep_id}: [{self.get_chan_sep()}]"


        

class ArchivedRPMessage(Base):
    __tablename__ = 'ArchivedRPMessages'

    message_id = Column(Integer, primary_key=True)
    author = Column(String);    avatar = Column(String)
    content = Column(String)
    created_at = Column(DateTime)
    channel = Column(String);    
    category = Column(String);    
    thread = Column(String, nullable=True)
    posted_url = Column(String)
    channel_sep_id = Column(Integer,ForeignKey('ChannelSeps.channel_sep_id'), nullable=True)
    server_id = Column(Integer)
    #superkey = Column(String, ForeignKey('ChannelSeps.superkey'))

    #channel_sep = relationship('ChannelSeps', back_populates='messages')
    files = relationship('ArchivedRPFile', backref='archived_rp_message')
    def get_chan_sep(self):
        return f"{self.category}-{self.channel}-{self.thread}"

    @staticmethod
    def add_or_update(message_id, **kwargs):
        session:Session=DatabaseSingleton.get_session()
        profile = session.query(ArchivedRPMessage).filter_by(message_id=message_id).first()
        if not profile:
            profile = ArchivedRPMessage(message_id=message_id)
            session.add(profile)
        for key, value in kwargs.items():
            setattr(profile, key, value)
        session.commit()

    def update(self, **kwargs):
        
        for key, value in kwargs.items():
            setattr(self, key, value)
        #session.add(self)
        #session.commit()
    @staticmethod
    def get_latest_archived_rp_message(session, server_id):
        """
        Returns the latest entry in the 'ArchivedRPMessage' table with the specified server ID.
        """
        session:Session=DatabaseSingleton.get_session()
        query = session.query(ArchivedRPMessage).filter_by(server_id=server_id).order_by(desc(ArchivedRPMessage.created_at)).first()
        return query
    @staticmethod
    def get_messages_without(server_id: int):
        session = DatabaseSingleton.get_session()
        return session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == server_id) &
            ((ArchivedRPMessage.channel_sep_id == None) | (ArchivedRPMessage.posted_url == None))
        ).order_by(ArchivedRPMessage.created_at).all()
    
    def add_file(self, archived_rp_file):
        session = DatabaseSingleton.get_session()
        session.add(archived_rp_file)
        session.commit()

    def remove_file(self, server_id, filename):
        session = DatabaseSingleton.get_session()
        for file in self.files:
            if file.server_id == server_id and file.filename == filename:
                session.delete(file)
                session.commit()
                return True
        return False
    def list_files(self):
        session = DatabaseSingleton.get_session()
        files = session.query(ArchivedRPFile).filter_by(message_id=self.message_id).all()
        return [file for file in files]
    def __repr__(self):
        return f"{self.author}: {self.content} [{self.created_at}] ([{self.get_chan_sep()}]: [{self.channel_sep_id}])"


class ArchivedRPFile(Base):
    __tablename__ = 'ArchivedRPFiles'

    message_id = Column(Integer, ForeignKey('ArchivedRPMessages.message_id', ondelete='CASCADE'))
    file_number = Column(Integer)
    filename = Column(String)
    bytes = Column(LargeBinary)
    description = Column(String)
    spoiler = Column(Boolean, default=False)
    #archived_rp_message = relationship('ArchivedRPMessage', backref='files')

    __table_args__ = (
        PrimaryKeyConstraint('message_id', 'file_number'),
    )
    def to_file(self):
        return discord.File(io.BytesIO(self.bytes),filename=self.filename,spoiler=self.spoiler,description=self.description)

def create_archived_rp_file(arpm, server_id, vekwargs):
    
    session = DatabaseSingleton.get_session()
    if arpm:
        archived_rp_file = ArchivedRPFile(message_id=arpm.message_id, file_number=server_id, **vekwargs)
        arpm.add_file(archived_rp_file)
        session.add(archived_rp_file)
        session.commit()
        return True
    return False

def create_history_pickle_dict(message):
    history_pickle_dict = {
        'message_id': message.id,
        'author': message.author.name,
        'avatar': None,
        'content': message.content,
        'created_at': message.created_at,
        'category': 'Uncategorized',
        'channel': message.channel.name,
        'thread': None,
        'channel_sep_id': None,
        'posted_url': None,
        'server_id': message.channel.guild.id
    }

    if message.author.avatar != None:
        if type(message.author.avatar) == str:
            history_pickle_dict['avatar'] = message.author.avatar.url
        else:
            history_pickle_dict['avatar'] = message.author.avatar.url

    channel = message.channel
    if channel.type == discord.ChannelType.public_thread:
        history_pickle_dict['thread'] = channel.name
        history_pickle_dict['channel'] = channel.parent.name

    if channel.category != None:
        history_pickle_dict['category'] = channel.category.name

    return history_pickle_dict

class HistoryMakers():
    @staticmethod
    async def get_history_message(thisMessage):
        fsize=0
        hmes=create_history_pickle_dict(thisMessage)
        id=hmes['server_id']
        ms=ArchivedRPMessage().add_or_update(**hmes)
        count=0
        for attach in thisMessage.attachments:
            if 'image' in attach.content_type:
                if attach.size+fsize<7000000:
                    count+=1
                    fd=await attach.to_file()
                    bytes=await attach.read()
                    fdv = {
                        "filename": fd.filename,
                        "bytes": bytes,
                        "description": fd.description,
                        "spoiler": fd.spoiler
                    }
                    create_archived_rp_file(ms,count,dummy_file=fdv)
                    fsize+=attach.size
        
        return hmes
    @staticmethod
    async def get_history_message_list(messages):
        '''add list of history messages to result.'''
        session = DatabaseSingleton.get_session()
        archived_rp_messages = []
        archived_rp_files = []
        for thisMessage in messages:
            
            hmes = create_history_pickle_dict(thisMessage)
            id = hmes['server_id']
            ms = ArchivedRPMessage(**hmes)
            
            filecount, fsize = 0,0
            for attach in thisMessage.attachments:
                if 'image' in attach.content_type:
                    if attach.size + fsize < 7000000:
                        filecount += 1
                        fd = await attach.to_file()
                        bytes = await attach.read()
                        fdv = {
                            "filename": fd.filename,
                            "bytes": bytes,
                            "description": fd.description,
                            "spoiler": fd.spoiler
                        }
                        rps = create_archived_rp_file(ms, filecount, dummy_file=fdv)
                        archived_rp_files.append(rps)
                        fsize += attach.size
            if thisMessage.content.isspace() and not filecount<=0:
                #Skip if no content or file.
                continue
            archived_rp_messages.append(ms)
        add_or_update_all(session,ArchivedRPMessage,archived_rp_messages)
        add_or_update_all(session,ArchivedRPFile,archived_rp_files)

        session.commit()
        return archived_rp_messages
    @staticmethod
    def get_history_message_sync(thisMessage,channel_sep=None):
        hmes=create_history_pickle_dict(thisMessage)
        return hmes

DatabaseSingleton('setup').load_base(Base)

'''
below should be equivalent to:
CREATE TRIGGER IF NOT EXISTS update_channel_sep_id
AFTER UPDATE OF channel_sep_id ON ArchivedRPMessages
BEGIN
    INSERT INTO ChannelSeps (channel_sep_id, server_id, channel, category, thread, created_at, posted_url)
    SELECT NEW.channel_sep_id, NEW.server_id, NEW.channel, NEW.category, NEW.thread, NEW.created_at, NEW.posted_url
    WHERE NOT EXISTS (
        SELECT 1 FROM ChannelSeps WHERE channel_sep_id = NEW.channel_sep_id
    );
END;
'''


@event.listens_for(ArchivedRPMessage.channel_sep_id, 'set')
def update_channel_sep_id_listener(target, value, oldvalue, initiator):
    if value != oldvalue and value!=None and target.server_id:
        session = Session.object_session(target)
        if session is None:
            raise exc.InvalidRequestError("Target is not attached to any session.")

        query = select(ChannelSep).where(ChannelSep.channel_sep_id == value and ChannelSep.server_id==target.server_id)
        if not session.query(query.exists()).scalar():

            channel_sep = ChannelSep(
                channel_sep_id=value,
                server_id=target.server_id,
                channel=target.channel,
                category=target.category,
                thread=target.thread,
                created_at=target.created_at
            )

            session.add(channel_sep)
            session.commit()
