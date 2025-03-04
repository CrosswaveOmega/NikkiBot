
import gui
from typing import Literal
import discord
import asyncio
import csv

# import datetime
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import event

from utility import (
    serverOwner,
    serverAdmin,
    seconds_to_time_string,
    get_time_since_delta,
    formatutil,
)
from utility import WebhookMessageWrapper as web, urltomessage, ConfirmView, RRuleView
from bot import (
    TCBot,
    TCGuildTask,
    Guild_Task_Functions,
    StatusEditMessage,
    TC_Cog_Mixin,
)
from random import randint
from discord.ext import commands, tasks

from dateutil.rrule import rrule, rrulestr, WEEKLY, SU, MINUTELY, HOURLY

from discord import app_commands
from discord.app_commands import Choice

from database.database_ai import AuditProfile, ServerAIConfig
from database import ServerArchiveProfile, DatabaseSingleton
from .ArchiveSub import (
    do_group,
    collect_server_history,
    check_channel,
    ArchiveContext,
    collect_server_history_lazy,
    setup_lazy_grab,
    lazy_archive,
    LazyContext,
    ChannelSep,
    ArchivedRPMessage,
    MessageTemplates,
    HistoryMakers,
    ChannelArchiveStatus,
)
from collections import defaultdict


class ToChoice(commands.Converter):
    async def convert(self, ctx, argument):
        if not ctx.interaction:
            if type(argument) == str:
                choice = Choice(name="fallback", value=argument)
                return choice
        else:
            return argument
        
def should_archive_channel(mode: int, chan:discord.TextChannel, profile, guild:discord.Guild):
    chan_ignore=profile.has_channel(chan.id)
    cat_ignore=chan.category and profile.has_channel(chan.category.id)
    if not (chan.permissions_for(guild.me).view_channel and chan.permissions_for(guild.me).read_message_history):
        return False, "NO PERMS"

    if mode == 0:
        return not chan_ignore and not cat_ignore, f"Mode {chan_ignore},{cat_ignore}"
    elif mode == 1:
        return chan_ignore, f"Mode {chan_ignore},{cat_ignore}"
    elif mode == 2:
        return cat_ignore and not bool(chan_ignore), f"Mode {chan_ignore},{cat_ignore}"

    return False, f"No mode at all..."

class ServerRPArchiveExtra(commands.Cog, TC_Cog_Mixin):
    """This class is intended for Discord RP servers that use Tupperbox or another proxy application.."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        self.private = True
        self.loadlock = asyncio.Lock()
        self.helptext = """Extra commands for server archiving.
        """
        self.manual_enable = True

    def cog_unload(self):
        # Remove the task function.
        pass

    @commands.command(extras={"guildtask": ["rp_history"]})
    async def count_messages_in_interval(self, ctx, timestamp: str):
        """Count messages within a 15-minute interval starting from the specified timestamp."""
        # Convert the timestamp string to a datetime object
        try:
            timestamp_datetime = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            await ctx.send(
                "Invalid timestamp format. Please use 'YYYY-MM-DD HH:MM:SS'."
            )
            return
        await ctx.send(f"<t:{int(timestamp_datetime.timestamp())}:f>")
        # Call the method to get messages within the 15-minute interval
        messages = ArchivedRPMessage.get_messages_within_15_minute_interval(
            ctx.guild.id, timestamp_datetime
        )

        # Send the count of messages in the interval
        await ctx.send(
            f"Number of messages in the 15-minute interval starting from {timestamp}: {len(messages)}"
        )
    
    @commands.command(extras={"guildtask": ["rp_history"]})
    async def check_message_archive_ignore(self,ctx):
        chantups = []
        guild=ctx.guild
        if not guild:
            await ctx.send("Must be in guild")
        chantups.extend(("forum", chan) for chan in guild.forums)

        chantups.extend(("textchan", chan) for chan in guild.text_channels)
        
        profile = ServerArchiveProfile.get_or_new(guild.id)
        mode=profile.get_ignore_mode()
        await ctx.send(f"Archive mode  {mode}")
        for tup, chan in chantups:
            doarchive=should_archive_channel(mode,chan,profile,guild)
            await ctx.send(f"Can archive {chan.name} {doarchive}")




async def setup(bot):
    gui.dprint(__name__)
    # from .ArchiveSub import setup
    # await bot.load_extension(setup.__module__)
    await bot.add_cog(ServerRPArchiveExtra(bot))


async def teardown(bot):
    # from .ArchiveSub import setup
    # await bot.unload_extension(setup.__module__)
    await bot.remove_cog("ServerRPArchiveExtra")
