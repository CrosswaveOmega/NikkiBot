from datetime import timezone, datetime
import json
import discord
import io

from typing import List, Optional, Union
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Boolean, Text, distinct, or_, update, func
from sqlalchemy import LargeBinary, ForeignKey,PrimaryKeyConstraint, insert, distinct
from sqlalchemy.orm import relationship, column_property
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased
from database import DatabaseSingleton, AwareDateTime,add_or_update_all
from sqlalchemy import select,event, exc

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc, asc, and_

'''

This script defines Tables that are used exclusively within the 
context of the ServerRPArchive Cog and it's ArchiveSub subpackage.

'''
from assets import AssetLookup
from utility import hash_string
ArchiveBase=declarative_base(name="Archive System Base")

class ChannelArchiveStatus(ArchiveBase):
    __tablename__='ChannelArchiveStatus'
    server_id=Column(Integer,primary_key=True)
    channel_id=Column(Integer,primary_key=True)
    thread_parent_id=Column(Integer,nullable=True)
    stored=Column(Integer,default=0)
    active_count=Column(Integer,default=0)
    first_message_time=Column(AwareDateTime(timezone=True),nullable=True)
    last_message_time=Column(AwareDateTime(timezone=True),nullable=True)
    latest_archive_time=Column(AwareDateTime(timezone=True),nullable=True)
    @staticmethod
    def get_by_tc(channel):
        server_id=channel.guild.id
        channel_id=channel.id
        new=ChannelArchiveStatus.get(server_id,channel_id)
        if not new:
            session=DatabaseSingleton.get_session()
            new = ChannelArchiveStatus(server_id=server_id,channel_id=channel_id)
            if channel.type!=discord.ChannelType.text:
                if channel.parent!=None:
                    new.thread_parent_id=channel.parent.id
            session.add(new)
            session.commit()
        return new

    @staticmethod
    def get(server_id, channel_id):
        session = DatabaseSingleton.get_session()
        return session.query(ChannelArchiveStatus).filter_by(server_id=server_id, channel_id=channel_id).first()
    @staticmethod
    def get_all(server_id, outdated=False):
        session = DatabaseSingleton.get_session()
        if outdated:
            filter = and_(
                ChannelArchiveStatus.server_id == server_id,
                or_(
                ChannelArchiveStatus.latest_archive_time==None,
                ChannelArchiveStatus.latest_archive_time < ChannelArchiveStatus.last_message_time
                )
                
            )
            query=session.query(ChannelArchiveStatus).filter(filter).all()
            return query
        query=session.query(ChannelArchiveStatus).filter_by(server_id=server_id).all()
        return query
    @staticmethod
    def get_total_unarchived_time(server_id):
        session = DatabaseSingleton.get_session()
        query=session.query(ChannelArchiveStatus).filter_by(server_id=server_id).all()
        if not query: return (datetime.now()-datetime.now())
        outcome=[s.get_time_between() for s in query]
        res=(datetime.now()-datetime.now())
        for o in outcome:res+=o
        return res
    async def get_first_and_last(self,channel:discord.TextChannel, force=False):
        if self.first_message_time==None or force:
            async for thisMessage in channel.history(oldest_first=True, limit=1):
                print(thisMessage.created_at,thisMessage.created_at.tzinfo)
                self.first_message_time=thisMessage.created_at
                #self.latest_archive_time=thisMessage.created_at
                
        if self.last_message_time==None or force:
            async for thisMessage in channel.history(oldest_first=False, limit=1):
                print(thisMessage.created_at,thisMessage.created_at.tzinfo)
                self.last_message_time=thisMessage.created_at
    def get_time_between(self):
        if self.latest_archive_time==None:
            if self.first_message_time==None:
                return(datetime.now()-datetime.now())
            return self.last_message_time-self.first_message_time
        return self.last_message_time-self.latest_archive_time
        
    def increment(self,date):
        self.stored += 1
        #print(self.last_message_time.tzinfo,date.tzinfo)
        if self.last_message_time<=date:
            self.last_message_time=date
        
        self.latest_archive_time = date
    def mod_active(self,incr):
        self.active_count+=incr
    def __str__(self):
        return f"{self.stored},{self.first_message_time},{self.latest_archive_time},{self.last_message_time}"

    def update_latest_date(self, date):
        session = DatabaseSingleton.get_session()
        session.commit()

class ChannelSep(ArchiveBase):
    '''Table for the channel separator objects.  Channel separators are used to group archived messages.'''
    __tablename__ = 'ChannelSeps'

    channel_sep_id = Column(Integer,primary_key=True)
    server_id = Column(Integer,primary_key=True, default=69)
    channel = Column(String)
    category = Column(String)
    thread = Column(String)

    all_ok=Column(Boolean, default=False)
    neighbor_count=Column(Integer, default=0)

    created_at = Column(AwareDateTime)
    posted_url = Column(String, nullable=True, default=None)
    message_count = Column(Integer,default=0)

    __table_args__ = (
        PrimaryKeyConstraint('channel_sep_id', 'server_id'),
    )
    def get_message_count(self):
        session:Session=DatabaseSingleton.get_session()
        count= session.query(func.count(ArchivedRPMessage.message_id)).filter(
            (ArchivedRPMessage.server_id == self.server_id) &
            (ArchivedRPMessage.channel_sep_id == self.channel_sep_id)
        ).scalar()
        return count
    def update_message_count(self):
        session:Session=DatabaseSingleton.get_session()
        count= session.query(func.count(ArchivedRPMessage.message_id)).filter(
            (ArchivedRPMessage.server_id == self.server_id) &
            (ArchivedRPMessage.channel_sep_id == self.channel_sep_id)
        ).scalar()
        self.message_count=count

    @staticmethod
    def add_channel_sep_if_needed(message,chansepid):
        '''if there's a new channel sep id, create a new channel sep.
        otherwise, return the channel sep id passed in.'''
        session: Session = DatabaseSingleton.get_session()
        # Check if a ChannelSep with the same server_id and channel_sep_id already exists
        existing_channel_sep = session.query(ChannelSep).filter_by(
            server_id=message.server_id,
            channel_sep_id=chansepid).first()
        if existing_channel_sep:
            existing_channel_sep.update_message_count()
            return existing_channel_sep
        channel_sep= ChannelSep.derive_from_archived_rp_message(message)
        session.add(channel_sep)
        session.commit()
        return channel_sep

    @staticmethod
    def derive_from_archived_rp_message(message):
        '''Create a new ChannelSep entry based on the passed in ArchivedRPMessage'''
        #session: Session = DatabaseSingleton.get_session()
        channel_sep = ChannelSep(
                channel_sep_id=message.channel_sep_id,
                server_id=message.server_id,
                channel=message.channel,
                category=message.category,
                thread=message.thread,
                created_at=message.created_at
            )
        return channel_sep

        
    @staticmethod
    def derive_channel_seps_mass(server_id: int):
        session: Session = DatabaseSingleton.get_session()
        # Query 1: Get distinct channel_sep_ids from ChannelSeps with server_id
        distinct_channel_sep_ids = (
            session.query(ChannelSep.channel_sep_id)
            .filter_by(server_id=server_id)
            .distinct()
            .all()
        )
        existing_channel_sep_ids = {id_[0] for id_ in distinct_channel_sep_ids}
        # Query 2: Get the first messages in ArchivedRPMessage with server_id and a distinct channel_sep_ids not in ChannelSeps
        distinct_messages = (
            session.query(func.min(ArchivedRPMessage.created_at))
            .filter(
                (ArchivedRPMessage.server_id == server_id) &
                (~ArchivedRPMessage.channel_sep_id.in_(existing_channel_sep_ids))
            )
            .group_by(ArchivedRPMessage.channel_sep_id)
            .all()
        )
        # Step 3: Derive new ChannelSeps based on the first messages
        new_channel_seps = []
        for message_id in distinct_messages:
            message = session.query(ArchivedRPMessage).get(message_id[0])
            new_channel_sep = ChannelSep.derive_from_archived_rp_message(message)
            session.add(new_channel_sep)
            new_channel_seps.append(new_channel_sep)
        session.commit()
        # Sort the new ChannelSeps by created_at attribute
        new_channel_seps.sort(key=lambda sep: sep.created_at)
        return new_channel_seps

    def get_chan_sep(self):
        return f"{self.category}-{self.channel}-{self.thread}"

    @staticmethod
    def delete_channel_seps_by_server_id(server_id: int):
        '''delete all channel seps that belong to the passed in server id'''
        session: Session = DatabaseSingleton.get_session()
        session.query(ChannelSep).filter(ChannelSep.server_id == server_id).delete()
        session.commit()


    @staticmethod
    def get_posted_but_incomplete(server_id: int):
        '''retrieve all ChannelSep objects that where posted, but not done retrieving messages.'''
        filter = and_(
            ChannelSep.posted_url != None,
            ChannelSep.server_id == server_id,
            ChannelSep.all_ok==False
        )
        session = DatabaseSingleton.get_session()
        return session.query(ChannelSep).filter(filter).order_by(ChannelSep.channel_sep_id).all()
    
    @staticmethod
    def get_unposted_separators(server_id: int,limit:int=None):
        '''retrieve up to `limit` ChannelSep objects for the passed in serverid that are not posted yet.'''
        filter = and_(
            ChannelSep.posted_url == None,
            ChannelSep.server_id == server_id
        )
        session = DatabaseSingleton.get_session()
        if limit==None:
            return session.query(ChannelSep).filter(filter).order_by(ChannelSep.channel_sep_id).all()
        else:
            return session.query(ChannelSep).filter(filter).order_by(ChannelSep.channel_sep_id).limit(limit).all()
    @staticmethod
    def get_all_separators(server_id: int):
        '''get all separators from the passed in channel sep.'''
        filter =            ChannelSep.server_id == server_id
        session = DatabaseSingleton.get_session()
        return session.query(ChannelSep).filter(filter).order_by(ChannelSep.created_at).all()
    @staticmethod
    def get_all_update_count(server_id: int):
        filter = ChannelSep.server_id == server_id
        session = DatabaseSingleton.get_session()
        for csep in session.query(ChannelSep).filter(filter).order_by(ChannelSep.created_at).all():
            if csep.message_count==None:
                csep.update_message_count()
        session.commit()
        return 
    
    @classmethod
    def get(cls, channel_sep_id, server_id):
        """
        Returns the entire Channel_sep entry for the specified server_id and channel_sep_id, or None if it doesn't exist.
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
    
    def create_embed(self, cfrom:Optional[str]=None,cto:Optional[str]=None):
        defaultstr="EOL⏹️" #For the Index/Channel Index
        defaultcstr="EOCL⏹️" #For the Index/Channel Index
        defaultclstr="FIRST" #For the Index/Channel Index
        cembed=discord.Embed(colour=discord.Colour(0x7289da))
        if cfrom:
            cembed=discord.Embed(colour=discord.Colour(0xd1113a))

        cembed.add_field(name="Category", value=self.category, inline=True)
        if self.thread!=None:
            cembed.add_field(name="ParentChannel", value=self.channel, inline=True)
            cembed.add_field(name="Thread", value=self.thread, inline=True)
            #categorytext+= "\n**Channel**"+current_channel.Parent.name
        else:
            cembed.add_field(name="Channel", value=self.channel, inline=True)
        cembed.timestamp= self.created_at
        utcdate=self.created_at.astimezone(timezone.utc);
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

        cembed.description="{} {} ░░░░░░░░░░░░░░░ {} channel {}".format(lastm, nextm, lastcm, nextcm)
        actorstr=", ".join(["`{}`".format(x) for x in charlist])
        if actorstr:
            if(len(actorstr)>1024): actorstr=actorstr[0:1023]
            cembed.add_field(name="Actors", value=actorstr, inline=False)
        if cfrom:
            cembed.add_field(name="Flashback to", value=f"{cfrom}", inline=False)
        if cto:
            cembed.add_field(name="Continued at", value=f"{cto}", inline=False)
        return cembed, count
    def __repr__(self):
        return f"{self.channel_sep_id}: [{self.get_chan_sep()}]"


class ArchivedRPMessage(ArchiveBase):
    '''represents an archived RP message for a specific server_id'''
    __tablename__ = 'ArchivedRPMessages'

    message_id = Column(Integer, primary_key=True)
    author = Column(String);    avatar = Column(String)
    content = Column(String)
    created_at = Column(AwareDateTime)
    channel = Column(String);    
    category = Column(String);    
    thread = Column(String, nullable=True)
    posted_url = Column(String)
    channel_sep_id = Column(Integer,ForeignKey('ChannelSeps.channel_sep_id'), nullable=True)
    server_id = Column(Integer)
    is_active = Column(Boolean, default=False)
    #channel_sep = relationship('ChannelSeps', back_populates='messages')
    files = relationship('ArchivedRPFile', backref='archived_rp_message')
    embed = relationship('ArchivedRPEmbed', backref='archived_rp_message_set')
    def get_chan_sep(self):
        return f"{self.category}-{self.channel}-{self.thread}"
    
    @staticmethod
    def get_archived_rp_messages_with_null_posted_url(server_id: int) -> List['ArchivedRPMessage']:
        session:Session=DatabaseSingleton.get_session()
        return session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == server_id) &
            (ArchivedRPMessage.posted_url.is_(None))
        ).all()
    
    @staticmethod
    def get_archived_rp_messages_without_null_posted_url(server_id: int) -> List['ArchivedRPMessage']:
        session:Session=DatabaseSingleton.get_session()
        return session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == server_id) &
            (ArchivedRPMessage.posted_url.is_not(None))
        ).all()
    
    @staticmethod
    def reset_channelsep_data(server_id: int):
        session: Session = DatabaseSingleton.get_session()
        stmt = update(ArchivedRPMessage).where(ArchivedRPMessage.server_id == server_id).values(
            posted_url=None,
            channel_sep_id=None
        )
        session.execute(stmt)
        session.commit()

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

    @staticmethod
    def get(server_id: int,message_id:int):
        '''get result from database.'''
        session = DatabaseSingleton.get_session()
        result= session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == server_id) &
            ((ArchivedRPMessage.message_id == message_id))
        ).order_by(ArchivedRPMessage.created_at).first()
        if result:
            if result.is_active:
                return 2, result
            return 1,result
        return 0,result

    @staticmethod
    def get_latest_archived_rp_message(server_id):
        session:Session=DatabaseSingleton.get_session()
        query = session.query(ArchivedRPMessage).filter_by(server_id=server_id).order_by(desc(ArchivedRPMessage.created_at)).first()
        return query
    @staticmethod
    def get_messages_without_group(server_id: int, upperlim=None):
        session = DatabaseSingleton.get_session()
        return session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == server_id) &
            ((ArchivedRPMessage.channel_sep_id == None))
        ).order_by(ArchivedRPMessage.created_at).limit(upperlim).all()
    @staticmethod
    def get_unique_chan_sep_ids(server_id: int):
        session: Session = DatabaseSingleton.get_session()
        query = session.query(distinct(ArchivedRPMessage.channel_sep_id)).filter_by(server_id=server_id).all()
        chan_sep_ids = [result[0] for result in query]
        return chan_sep_ids
    @staticmethod
    def get_messages_in_group(server_id: int,channel_sep_id:int):
        session = DatabaseSingleton.get_session()
        return session.query(ArchivedRPMessage).filter(
            (ArchivedRPMessage.server_id == server_id) &
            ((ArchivedRPMessage.channel_sep_id == channel_sep_id))
        ).order_by(ArchivedRPMessage.created_at).all()
    @staticmethod
    def count_all(server_id: int):
        session = DatabaseSingleton.get_session()
        session:Session=DatabaseSingleton.get_session()
        count= session.query(func.count(ArchivedRPMessage.message_id)).filter(
                (ArchivedRPMessage.server_id == server_id) 
        ).scalar()
        return count
    @staticmethod
    def count_all_without_group(server_id: int):
        session = DatabaseSingleton.get_session()
        session:Session=DatabaseSingleton.get_session()
        count= session.query(func.count(ArchivedRPMessage.message_id)).filter(
                (ArchivedRPMessage.server_id == server_id) & (ArchivedRPMessage.channel_sep_id == None)
        ).scalar()
        return count
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
    def get_embed(self):
        session = DatabaseSingleton.get_session()
        embed_attr = session.query(ArchivedRPEmbed).filter_by(message_id=self.message_id).first()
        embeds=[]
        if embed_attr: embeds=[embed_attr.to_embed()]
        return embeds
    def __repr__(self):
        return f"{self.author}: {self.content} [{self.created_at}] ([{self.get_chan_sep()}]: [{self.channel_sep_id}])"


class ArchivedRPFile(ArchiveBase):
    '''Represents a file uploaded with a message.'''
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
class ArchivedRPEmbed(ArchiveBase):
    '''represents (one) embed saved in a JSON string.'''
    __tablename__ = 'ArchivedRPEmbed'

    message_id = Column(Integer, ForeignKey('ArchivedRPMessages.message_id', ondelete='CASCADE'))
    embed_json=Column(String)
    #archived_rp_message_set = relationship('ArchivedRPMessage', backref='embed')

    __table_args__ = (
        PrimaryKeyConstraint('message_id'),
    )
    def to_embed(self):
        # Load the JSON string into a dictionary
        embed_dict = json.loads(self.embed_json)

        # Create the embed from the dictionary
        embed = discord.Embed.from_dict(embed_dict)
        return embed

def create_archived_rp_file(arpm, file_num, vekwargs):
    session = DatabaseSingleton.get_session()
    if arpm:
        archived_rp_file = ArchivedRPFile(message_id=arpm.message_id, file_number=file_num, **vekwargs)
        return archived_rp_file
    return None

def create_archived_rp_embed(arpm, embed):
    embed_dict = embed.to_dict()
    json_string = json.dumps(embed_dict)
    if arpm:
        archived_rp_emb = ArchivedRPEmbed(message_id=arpm.message_id, embed_json=json_string)
        return archived_rp_emb
    return None


def create_history_pickle_dict(message, over=None):
    #This code once saved Discord messages into a serialized object, which is why 
    #It's called history_pickle_dict

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
    if over:
        history_pickle_dict['created_at']=over['created_at']
    if not message.author.bot:
        hash, int=hash_string(message.author.name)
        name_list = AssetLookup.get_asset('blanknames')
        random_name = name_list[int % len(name_list)]
        history_pickle_dict['author']=f"{random_name}_{hash}"
        history_pickle_dict['avatar']=AssetLookup.get_asset('generic', 'urls')
    else:
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
    async def get_history_message(thisMessage,active=False):
        fsize=0
        session = DatabaseSingleton.get_session()
        hmes=create_history_pickle_dict(thisMessage)
        id=hmes['server_id']
        if active: hmes['is_active']=True
        filecount,fchecksize=0,0
        for attach in thisMessage.attachments:
            if 'image' in attach.content_type:
                if attach.size+fchecksize<7000000:
                    filecount+=1
                    fchecksize+=attach.size
        if thisMessage.content.isspace() and not filecount<=0 and not thisMessage.embeds:
            return 'skip'
        ms=ArchivedRPMessage().add_or_update(**hmes)
        count=0
        if thisMessage.embeds:
            #Only one embed.
            embed=thisMessage.embeds[0]
            embedv=create_archived_rp_embed(ms,embed)
            session.add(embedv)
            hasembed=True

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
                    file=create_archived_rp_file(ms,count,dummy_file=fdv)
                    session.add(file)
                    fsize+=attach.size
        session.commit()
        return hmes
    @staticmethod
    async def get_history_message_list(messages):
        '''add list of history messages to result.'''
        session = DatabaseSingleton.get_session()
        archived_rp_messages = []
        archived_rp_embeds=[]
        archived_rp_files = []
        for thisMessage_v in messages:
            thisMessage=thisMessage_v
            over=None
            if isinstance(thisMessage_v,dict):
                thisMessage=thisMessage_v['m']
                over=thisMessage_v
            mes=discord.Message
            hmes = create_history_pickle_dict(thisMessage,over)
            id = hmes['server_id']
            ms = ArchivedRPMessage(**hmes)
            hasembed=False
            if thisMessage.embeds:
                #Only want
                embed=thisMessage.embeds[0]
                embedv=create_archived_rp_embed(ms,embed)
                archived_rp_embeds.append(embedv)
                hasembed=True

            filecount, fsize = 0,0
            for attach in thisMessage.attachments:
                try:
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
                            rps = create_archived_rp_file(ms, filecount, vekwargs=fdv)
                            archived_rp_files.append(rps)
                            fsize += attach.size
                except Exception as e:
                    print(e)
            if thisMessage.content.isspace() and not filecount<=0 and not hasembed:
                #Skip if no content or file.
                continue
            archived_rp_messages.append(ms)
        add_or_update_all(session,ArchivedRPMessage,archived_rp_messages)
        add_or_update_all(session,ArchivedRPEmbed,archived_rp_embeds)
        add_or_update_all(session,ArchivedRPFile,archived_rp_files)

        session.commit()
        return archived_rp_messages
    @staticmethod
    def get_history_message_sync(thisMessage,channel_sep=None):
        hmes=create_history_pickle_dict(thisMessage)
        return hmes
    @staticmethod
    def add_channel_sep_if_needed(targetmessage,value):
        ChannelSep.add_channel_sep_if_needed(targetmessage,value)
        '''
        session=DatabaseSingleton.get_session()
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
            session.commit()'''

DatabaseSingleton('setup').load_base(ArchiveBase)

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
"""

@event.listens_for(ArchivedRPMessage.channel_sep_id, 'set')
def update_channel_sep_id_listener(target, value, oldvalue, initiator):
    if value != oldvalue and value!=None and target.server_id:
        HistoryMakers.add_channel_sep_if_needed(target,value)
""" 