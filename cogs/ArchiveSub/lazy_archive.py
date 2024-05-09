import time
from .archive_compiler import ArchiveCompiler, ArchiveProgress
from .historycollect import collect_server_history_lazy
from .archive_database import ChannelSep, ArchivedRPMessage, ChannelArchiveStatus
from .collect_group_index import do_group
from database import ServerArchiveProfile
from bot import (
    TCBot,
    TCGuildTask,
    Guild_Task_Functions,
    StatusEditMessage,
    TC_Cog_Mixin,
)
from utility import WebhookMessageWrapper as web, urltomessage, ConfirmView, RRuleView
from utility import (
    serverOwner,
    serverAdmin,
    seconds_to_time_string,
    get_time_since_delta,
    formatutil,
)
import asyncio
import gui
from datetime import timezone, datetime
import json
import discord
import io
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Boolean,
    Text,
    distinct,
    or_,
    update,
    func,
)

from database import DatabaseSingleton, AwareDateTime, add_or_update_all
from sqlalchemy import select, event, exc

from sqlalchemy.orm import declarative_base
from sqlalchemy import desc, asc, and_

"""
RP archives is done within three phases: collecting, grouping, and then posting.
The regular RP archive, designed to update a pre-existing RP archive, typically does these phases back to back.
While this works for updating the archives, it does not work for creating whole new archives.
Creating a whole new archive can take several weeks depending on the amount of valid archivable messages within a server.

As such, a 'lazy' variant of the RP archive system was designed.

The lazy archive preforms each phase for about 15 minutes, then takes a pause.
This reduces the  load on the server and system resources, and leaves the bot open for 
preforming other tasks in the meantime.
"""
from assets import AssetLookup
from utility import hash_string

LazyBase = declarative_base(name="Archive System LazyMode Base")


class LazyContext(LazyBase):
    __tablename__ = "lazy_context"

    server_id = Column(String, primary_key=True)
    active_id = Column(String, nullable=True)
    collected = Column(Boolean, default=False)
    grouped = Column(Boolean, default=False)
    posting = Column(Boolean, default=False)
    message_count = Column(Integer, default=0)
    archived_so_far = Column(Integer, default=0)
    group_count = Column(Integer, default=0)
    grouped_so_far = Column(Integer, default=0)
    state = Column(String, default="collecting")

    def __repr__(self):
        return f"LazyContext({self.server_id},active={self.active_id}, state={self.state},message_count={self.message_count}, archived={self.archived_so_far})"

    @staticmethod
    def create(server_id):
        session = DatabaseSingleton.get_session()
        lazy_context = LazyContext(server_id=server_id)
        lazy_context.active_id = server_id
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
        self.archived_so_far += 1
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


DatabaseSingleton("setup").load_base(LazyBase)


async def lazy_archive(self, ctx):
    """Equivalient to compile_archive, but does each step in subsequent calls of itself."""
    MESSAGES_PER_POST_CALL = 150
    CHANNEL_SEPS_PER_CLUSTER = 5
    MAX_TOTAL_MINUTES = ctx.bot.config.get("archive", "max_lazy_archive_minutes")
    if MAX_TOTAL_MINUTES == None:
        MAX_TOTAL_MINUTES = "15"
    MAX_TOTAL_SECONDS = max(int(MAX_TOTAL_MINUTES) * 60, 60)

    # roughly five minutes worth of messages
    started_at = time.monotonic()

    def upper_time_limit(ext=0):
        delta = time.monotonic() - started_at
        remaining = MAX_TOTAL_SECONDS - delta
        if ext > remaining:
            return max(remaining + ext, 0)
        return max(remaining, 0)

    arc_comp = ArchiveCompiler(ctx,lazymode=True)
    bot = ctx.bot
    channel = ctx.message.channel
    guild: discord.Guild = channel.guild
    guildid = guild.id

    lazycontext = LazyContext.get(guildid)
    if not lazycontext:
        return False
    if lazycontext.active_id:
        guildid = int(lazycontext.active_id)

    # Select state
    while upper_time_limit():
        out = await arc_comp.setup()
        if lazycontext.state == "setup":
            lazycontext.next_state()
        elif lazycontext.state == "collecting":
            if lazycontext.collected:
                lazycontext.message_count = ArchivedRPMessage.count_all(
                    server_id=guild.id
                )
                lazycontext.next_state()
                return True
            statusMessToEdit = await channel.send(f"Commencing Lazy Archive Run")
            statmess = StatusEditMessage(statusMessToEdit, ctx)
            while upper_time_limit() > 0:
                bot.add_act(
                    str(guild.id) + "lazyarch",
                    f"Time={seconds_to_time_string(upper_time_limit())}",
                )

                st = None
                still_collecting, st = await collect_server_history_lazy(
                    ctx, statmess, update=True
                )
                if not still_collecting:
                    await ctx.send("Gather phase completed.")
                    lazycontext.next_state()
                    break
                bot.remove_act(str(guild.id) + "lazyarch")
            await statmess.delete()

        elif lazycontext.state == "grouping":
            if lazycontext.grouped:
                lazycontext.next_state()
                return True
            lazycontext.message_count = ArchivedRPMessage.count_all(server_id=guildid)

            bot.database.get_session().commit()
            m, profile, archive_channel = arc_comp.supertup
            fc, gid, ts = await arc_comp.group(m, profile)
            lazycontext.message_count = fc
            lazycontext.archived_so_far = 0
            lazycontext.group_count = gid
            lazycontext.grouped_so_far = 0
            await m.edit(content=f"{fc}, seps, {gid}, {ts}")
            lazycontext.next_state()
        elif lazycontext.state == "posting":
            if lazycontext.posting:
                lazycontext.next_state()
                return True

            m, profile, archive_channel = arc_comp.supertup
            archive_channel = bot.get_channel(profile.history_channel_id)

            m, profile, archive_channel = arc_comp.supertup
            # archived_this_session<=MESSAGES_PER_POST_CALL
            # while upper_time_limit() > 0:
            allp=ArchiveProgress(lazycontext.message_count,lazycontext.group_count,lazycontext.archived_so_far,lazycontext.grouped_so_far,profile=profile)
            arc_comp.timeoff = allp
            did = await arc_comp.post(m, profile, archive_channel, MAX_TOTAL_SECONDS)
            lazycontext.archived_so_far += arc_comp.ap.m_arc
            lazycontext.grouped_so_far += arc_comp.ap.g_arc
            if not did:
                lazycontext.next_state()

            await arc_comp.cleanup(profile)
            await m.delete()
        elif lazycontext.state == "done":
            LazyContext.remove(guildid)
            return False
    return True
