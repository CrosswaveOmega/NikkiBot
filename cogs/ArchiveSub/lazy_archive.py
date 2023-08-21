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
RP archives is done within three phases: collecting, grouping, and then posting.
The regular RP archive, designed to update a pre-existing RP archive, typically does these phases back to back.
While this works for updating the archives, it does not work for creating whole new archives.
Creating a whole new archive can take several weeks depending on the amount of valid archivable messages within a server.

As such, a 'lazy' variant of the RP archive system was designed.

The lazy archive preforms each phase for about 15 minutes, then takes a pause.
This reduces the  load on the server and system resources, and leaves the bot open for 
preforming other tasks in the meantime.
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
        return f"LazyContext({self.server_id},active={self.active_id}, state={self.state},message_count={self.message_count}, archived={self.archived_so_far})"

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
        CHANNEL_SEPS_PER_CLUSTER=5
        MAX_TOTAL_MINUTES=ctx.bot.config.get('archive','max_lazy_archive_minutes')
        if MAX_TOTAL_MINUTES==None:
            MAX_TOTAL_MINUTES= '15'
        MAX_TOTAL_SECONDS=max(int(MAX_TOTAL_MINUTES)*60,60)


        #roughly five minutes worth of messages
        started_at=discord.utils.utcnow()
        def upper_time_limit(ext=0):
            delta=discord.utils.utcnow()-started_at
            remaining=MAX_TOTAL_SECONDS-delta.total_seconds()
            if ext>remaining:
               return max(remaining+ext,0)
            return max(remaining,0)
        bot = ctx.bot
        channel = ctx.message.channel
        guild:discord.Guild=channel.guild
        guildid=guild.id
        
        lazycontext=LazyContext.get(guildid)
        if not lazycontext:    return False
        if lazycontext.active_id:   guildid=int(lazycontext.active_id)
        profile=ServerArchiveProfile.get_or_new(guildid)
        gui.gprint(lazycontext.state)
        if lazycontext.state=='setup':
            lazycontext.next_state()
        elif lazycontext.state=='collecting':
            if lazycontext.collected:
                lazycontext.message_count=ArchivedRPMessage.count_all(server_id=guildid)
                lazycontext.next_state()
                return True
            statusMessToEdit=await channel.send(f"Commencing Lazy Archive Run")
            statmess=StatusEditMessage(statusMessToEdit,ctx)
            while upper_time_limit()>0:
                bot.add_act(str(guildid)+"lazyarch",f"Time={seconds_to_time_string(upper_time_limit())}")

                st==None
                still_collecting,st=await collect_server_history_lazy(
                    ctx,statmess,
                    update=True
                )
                if not still_collecting:
                    await ctx.send("Gather phase completed.")
                    lazycontext.next_state()
                    break
            bot.remove_act(str(guildid)+"lazyarch")
            await statmess.delete()
            return True
        
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
            
            me=await ctx.channel.send(content=f"<a:LetWalk:1118184074239021209> currently on {lazycontext.archived_so_far}/{lazycontext.message_count}, will take {seconds_to_time_string(upper_time_limit())} this session.")
            mt=StatusEditMessage(me,ctx)
            #archived_this_session<=MESSAGES_PER_POST_CALL
            while upper_time_limit()>0:
                
                needed=ChannelSep.get_posted_but_incomplete(guildid)
                grouped=ChannelSep.get_unposted_separators(guildid,limit=CHANNEL_SEPS_PER_CLUSTER)
                gui.gprint(f"Group length: {len(grouped)}")
                if len(grouped)<=0:
                    #Limit by day
                    session=DatabaseSingleton.get_session()
                    query = session.query(func.date(ArchivedRPMessage.created_at), func.count()).\
                    filter((ArchivedRPMessage.server_id == guildid)&(ArchivedRPMessage.channel_sep_id == None)).\
                    group_by(func.date(ArchivedRPMessage.created_at))
                    message_counts = query.limit(40).all()
                    await ctx.send(str(message_counts))
                    gui.gprint(message_counts)
                    if message_counts==None:
                        await ctx.send(f"All {fullcount} messages posted. ")
                        lazycontext.next_state()
                        return True
                    thelim=0
                    await ctx.send(message_counts)
                    for mc in message_counts:
                        day, count = mc
                        gui.gprint(f"{day}, {count}")
                        if count>0:  
                            thelim+=count
                    if thelim<=0:
                        await ctx.send("Limit is 0?")
                        return

                    if thelim<=0:
                        await ctx.send(f"All {fullcount} messages posted. ")
                        lazycontext.next_state()
                        return True
                    lastgroup=profile.last_group_num
                    ts,group_id=await do_group(guildid,profile.last_group_num, ctx=ctx,upperlim=thelim)
                    profile.update(last_group_num=group_id)
                    await ctx.channel.send(f"group has changed: {lastgroup}->{group_id}")
                    ChannelSep.get_all_update_count(guildid,200)
                    grouped=ChannelSep.get_unposted_separators(guildid,limit=CHANNEL_SEPS_PER_CLUSTER)
                bot.add_act(str(guildid)+"lazyarch",f"Time={seconds_to_time_string(upper_time_limit())}")
                if needed:
                    newgroup=[]
                    newgroup.extend(needed)
                    newgroup.extend(grouped)
                    grouped=newgroup
                allgroups=profile.last_group_num
                message_total=0
                gui.gprint(archive_channel.name)
                length=len(grouped)
                for sep in grouped: message_total+=sep.get_message_count()
                #Time between each message
                total_time_for_cluster=message_total*timebetweenmess
                #time between each delay.
                total_time_for_cluster+=(length*2)

                for e,sep in enumerate(grouped):
                    #Start posting
                    bot.add_act(str(guildid)+"lazyarch",f"groupid on {sep.channel_sep_id}/{allgroups}.\n  at least {seconds_to_time_string(upper_time_limit(total_time_for_cluster))} remaining.")
                    gui.gprint(e,sep)
                    startedsep=datetime.now()
                    if not sep.posted_url:
                        currjob="rem: {}".format(seconds_to_time_string(int(remaining_time_float)))
                        emb,count=sep.create_embed()
                        chansep=await archive_channel.send(embed=emb)
                        sep.update(posted_url=chansep.jump_url)
                        await self.edit_embed_and_neighbors(sep)
                        self.bot.database.commit()
                        duration=datetime.now()-startedsep
                        gui.gprint(f"Gui print took at least {str(duration)}")
                    elif sep.posted_url and not sep.all_ok:
                        old_message=await urltomessage(sep.posted_url,bot)
                        emb,count=sep.create_embed(cfrom=sep.posted_url)
                        new_message=await archive_channel.send(embed=emb)
                        jump_url=new_message.jump_url
                        embedit,count=sep.create_embed(cto=jump_url)
                        await old_message.edit(embed=embedit)
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
                        print(f"groupid: {sep.channel_sep_id}/{allgroups}.\n messages:{lazycontext.archived_so_far}/{lazycontext.message_count}\n  at least {seconds_to_time_string(upper_time_limit(total_time_for_cluster))} remaining.")
                        await mt.editw(min_seconds=45,content=f"<a:LetWalk:1118184074239021209> currently on {lazycontext.archived_so_far}/{lazycontext.message_count}, remaining session time is at least {seconds_to_time_string(upper_time_limit(total_time_for_cluster))}")
                        
                    sep.update(all_ok=True)
                    self.bot.database.commit()
                    await asyncio.sleep(2)
                    print(f"groupid: {sep.channel_sep_id}/{allgroups}.\n messages:{lazycontext.archived_so_far}/{lazycontext.message_count}\n  at least {seconds_to_time_string(upper_time_limit(total_time_for_cluster))} remaining.")
                    await mt.editw(min_seconds=5,content=f"<a:LetWalk:1118184074239021209> currently on {lazycontext.archived_so_far}/{lazycontext.message_count},remaining session time is at least {seconds_to_time_string(upper_time_limit(total_time_for_cluster))}")
                bot.remove_act(str(guildid)+"lazyarch")
            await me.delete()
        elif lazycontext.state=='done':
            LazyContext.remove(guildid)
            return False
        return True