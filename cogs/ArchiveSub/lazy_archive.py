from datetime import timezone, datetime
import json
import discord
import io
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Boolean, Text, distinct, or_, update, func

from database import DatabaseSingleton, AwareDateTime,add_or_update_all
from sqlalchemy import select,event, exc

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc, asc, and_

'''

This script defines Tables that are used exclusively within the 
context of the ServerRPArchive Cog and it's ArchiveSub subpackage.
H
'''
from assets import AssetLookup
from utility import hash_string
LazyBase=declarative_base(name="Archive System LazyMode Base")

class LazyContext(LazyBase):
    __tablename__ = 'lazy_context'

    server_id = Column(String, primary_key=True)
    active_id = Column(String, nullable=True)
    collected = Column(Boolean, default=False)
    grouped = Column(Boolean, default=False)
    posting = Column(Boolean, default=False)
    message_count = Column(Integer,default=0)
    archived_so_far = Column(Integer,default=0)
    state = Column(String, default="setup")

    def __repr__(self):
        return f"<LazyContext(server_id={self.server_id}, state={self.state})>"

    @staticmethod
    def create(server_id):
        session = DatabaseSingleton.get_session()
        lazy_context = LazyContext(server_id=server_id)
        lazy_context.active_id=server_id
        session.add(lazy_context)
        session.commit()
        return lazy_context

    @staticmethod
    def get(server_id):
        session = DatabaseSingleton.get_session()
        lazy_context = session.query(LazyContext).filter_by(server_id=server_id).first()
        return lazy_context

    @staticmethod
    def remove(server_id):
        session = DatabaseSingleton.get_session()
        lazy_context = session.query(LazyContext).filter_by(server_id=server_id).first()
        if lazy_context:
            session.delete(lazy_context)
            session.commit()
    def increment_count(self):
        self.archived_so_far+=1
        session = DatabaseSingleton.get_session()
        
    def next_state(self):
        if self.state == "setup":
            self.state = "collecting"
        elif self.state == "collecting":
            self.state = "grouping"
        elif self.state == "grouping":
            self.state = "posting"
        elif self.state == "posting":
            self.state = "done"

        session = DatabaseSingleton.get_session()
        session.commit()
        return self.state
    def __repr__(self):
        return f"{self.server_id}, {self.state},{self.message_count},{self.archived_so_far}"

DatabaseSingleton('setup').load_base(LazyBase)

import gui
import discord

import asyncio

from utility import serverOwner, serverAdmin, seconds_to_time_string, get_time_since_delta, formatutil
from utility import WebhookMessageWrapper as web, urltomessage, ConfirmView, RRuleView
from bot import TCBot, TCGuildTask, Guild_Task_Functions, StatusEditMessage, TC_Cog_Mixin



from database import ServerArchiveProfile
from .collect_group_index import do_group
from .archive_database import ChannelSep, ArchivedRPMessage, ChannelArchiveStatus
from .historycollect import collect_server_history_lazy

async def lazy_archive(self, ctx):
        """Equivalient to compile_archive, but does each step in subsequent calls of itself.             
        """
        MESSAGES_PER_POST_CALL=150
        #roughly five minutes worth of messages
        bot = ctx.bot
        channel = ctx.message.channel
        guild:discord.Guild=channel.guild
        guildid=guild.id

        lazycontext=LazyContext.get(guildid)
        if not lazycontext:
            return False
        if lazycontext.active_id:
            guildid=int(lazycontext.active_id)
        profile=ServerArchiveProfile.get_or_new(guildid)
        gui.gprint(lazycontext.state)
        if lazycontext.state=='setup':
            lazycontext.next_state()
        elif lazycontext.state=='collecting':
            if lazycontext.collected:
                lazycontext.message_count=ArchivedRPMessage.count_all(server_id=guildid)
                lazycontext.next_state()
                return True
            still_collecting=await collect_server_history_lazy(
                ctx,
                update=True
            )
            if not still_collecting:
                await ctx.send("Gather phase completed.")
                
                lazycontext.next_state()
        
        elif lazycontext.state=='grouping':
            if lazycontext.grouped:
                lazycontext.next_state()
                return True
            lazycontext.message_count=ArchivedRPMessage.count_all(server_id=guildid)
            bot.database.get_session().commit()

            lazycontext.next_state()
        elif lazycontext.state=='posting':
            if lazycontext.posting:
                lazycontext.next_state()
                return True
            archive_channel=bot.get_channel(profile.history_channel_id)
            timebetweenmess=2.0
            characterdelay=0.05
            fullcount=lazycontext.message_count-lazycontext.archived_so_far
            remaining_time_float= fullcount* timebetweenmess
            archived_this_session=0
            me=await ctx.channel.send(content=f"<a:LetWalk:1118184074239021209> currently on {lazycontext.archived_so_far}/{lazycontext.message_count}, will take{seconds_to_time_string(remaining_time_float)}, Will archive at least {MESSAGES_PER_POST_CALL-archived_this_session} messages if available.")
            mt=StatusEditMessage(me,ctx)
            while archived_this_session<=MESSAGES_PER_POST_CALL:
                lastgroup=profile.last_group_num
                ts,group_id=await do_group(guildid,profile.last_group_num, ctx=ctx,glimit=8,upperlim=1000)
                profile.update(last_group_num=group_id)
                await ctx.channel.send(f"{lastgroup}->{group_id}")
                needed=ChannelSep.get_posted_but_incomplete(guildid)
                grouped=ChannelSep.get_unposted_separators(guildid,limit=8)
                if len(grouped)<=0:
                    await ctx.send(f"All {fullcount} messages posted. ")
                    lazycontext.next_state()
                    return True
                
                gui.gprint(archive_channel.name)
                length=len(grouped)
                for e,sep in enumerate(grouped):
                    #Start posting
                    gui.gprint(e,sep)
                    if not sep.posted_url:
                        currjob="rem: {}".format(seconds_to_time_string(int(remaining_time_float)))
                        emb,count=sep.create_embed()
                        chansep=await archive_channel.send(embed=emb)
                        sep.update(posted_url=chansep.jump_url)
                        await self.edit_embed_and_neighbors(sep)
                        self.bot.database.commit()
                    for amess in sep.get_messages():
                        c,au,av=amess.content,amess.author,amess.avatar
                        files=[]
                        for attach in amess.list_files():
                            this_file=attach.to_file()
                            files.append(this_file)

                        webhookmessagesent=await web.postWebhookMessageProxy(archive_channel, message_content=c, display_username=au, avatar_url=av, embed=amess.get_embed(), file=files)
                        if webhookmessagesent:
                            amess.update(posted_url=webhookmessagesent.jump_url)
                            

                        await asyncio.sleep(timebetweenmess)
                        remaining_time_float=remaining_time_float-(timebetweenmess)
                        lazycontext.increment_count()
                        archived_this_session+=1
                        await mt.editw(min_seconds=45,content=f"<a:LetWalk:1118184074239021209> currently on {lazycontext.archived_so_far}/{lazycontext.message_count}, will take{seconds_to_time_string(remaining_time_float)}.\nWill archive at least {MESSAGES_PER_POST_CALL-archived_this_session} messages if available.")
                    sep.update(all_ok=True)
                    self.bot.database.commit()
                    await asyncio.sleep(2)
                    await mt.editw(min_seconds=5,content=f"<a:LetWalk:1118184074239021209> currently on {lazycontext.archived_so_far}/{lazycontext.message_count},will take{seconds_to_time_string(remaining_time_float)}.\nWill archive at least {MESSAGES_PER_POST_CALL-archived_this_session} messages if available.")
            await me.delete()
        elif lazycontext.state=='done':
            LazyContext.remove(guildid)
            return False
        return True