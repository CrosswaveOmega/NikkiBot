import gui
import asyncio
from datetime import datetime, timezone
from typing import List, Tuple

from .archive_database import HistoryMakers, ChannelArchiveStatus
from database import ServerArchiveProfile
import discord
from bot import StatusEditMessage
import utility.formatutil as futil
from discord import ChannelType as ct
from discord.ext import commands
import re

"""
Collects all messages in non-blacklisted channels, and adds them to the database in batches of 10.

"""
BATCH_SIZE = 9000
LAZYGRAB_LIMIT = 10000


def remove_lines_starting_with_gt(text):
    return re.sub(r"^> .*\n?", "", text, flags=re.MULTILINE)


def should_archive_channel(
    mode: int, chan: discord.TextChannel, profile, guild: discord.Guild
):
    chan_ignore = profile.has_channel(chan.id)
    cat_ignore = chan.category and profile.has_channel(chan.category.id)
    if not (
        chan.permissions_for(guild.me).view_channel
        and chan.permissions_for(guild.me).read_message_history
    ):
        return False

    if mode == 0:
        return not chan_ignore and not cat_ignore
    elif mode == 1:
        return chan_ignore
    elif mode == 2:
        return cat_ignore and not bool(chan_ignore)

    return False


class ArchiveContext:
    """This class defines the context within which an archive operation is performed.

    It manages various operational parameters and provides utility methods to
    analyze messages and channels during the archiving process.
    """

    def __init__(
        self,
        bot,
        status_mess=None,
        last_stored_time=None,
        update=False,
        profile=None,
        total_archived=0,
        channel_count=0,
        channel_spot=0,
        character_len=0,
        latest_time=None,
        total_ignored=0,
        color=0,
        lazy=False,
    ):
        """Initializes the ArchiveContext instance.

        Args:
            bot: The bot.
            status_mess: Status message of ongoing archival process.
            last_stored_time: Last recorded timestamp of the archive process.
            update: Boolean flag indicating if an update operation is to be performed.
            profile: Server profile to use for the archive context.
            total_archived: Total count of messages archived.
            channel_count: Total count of channels scanned.
            channel_spot: Current position in the list of channels to be scanned.
            character_len: Length of message content archived.
            latest_time: Latest timestamp of message archived.
            total_ignored: Total count of messages ignored during the archival process.
        """
        self.bot = bot
        self.status_mess: StatusEditMessage = status_mess
        self.last_stored_time = last_stored_time
        self.update = update
        self.profile = profile
        self.scope = profile.archive_scope
        self.channel_count = channel_count
        self.total_archived = total_archived
        self.channel_spot = channel_spot
        self.character_len = character_len
        self.latest_time = latest_time
        self.total_ignored = total_ignored
        self.server_color = color
        self.collect_limit = None
        self.lazy = lazy
        if self.lazy:
            self.collect_limit = LAZYGRAB_LIMIT

    def evaluate_add(self, thisMessage):
        """Determines whether a message should be added based on scope.

        Args:
            thisMessage: Message to evaluate.

        Returns:
            A boolean value indicating whether the message should be added.
        """
        add_check = False
        if self.scope == "both":
            add_check = True
        elif self.scope == "ws":
            add_check = (thisMessage.author.bot) and (
                thisMessage.author.id != self.bot.user.id
            )
        elif self.scope == "user":
            add_check = not (thisMessage.author.bot)
        return add_check

    def evaluate_channel(self, thisMessage):
        """Evaluates if the channel of the message is valid for archival.

        Args:
            thisMessage: Message whose channel needs to be evaluated.

        Returns:
            A boolean value indicating whether the channel is valid for archival.
        """
        guild = thisMessage.channel.guild
        chan = thisMessage.channel
        if chan.type in [ct.public_thread, ct.private_thread, ct.news_thread]:
            chan = chan.parent
        gui.gprint(chan.id, self.profile.has_channel(chan.id))
        should = should_archive_channel(
            self.profile.get_ignore_mode(), chan, self.profile, guild
        )
        # if (
        #     self.profile.has_channel(chan.id) == False
        #     and chan.permissions_for(guild.me).view_channel == True
        #     and chan.permissions_for(guild.me).read_message_history == True
        # ):
        #     return True
        return should

    def alter_latest_time(self, new):
        """Updates the latest_time with the maximum of the current latest_time and the new value.

        Args:
            new: New time to compare with latest_time.
        """
        self.latest_time = max(new, self.latest_time)

    async def get_first_time(
        self, cobj: discord.TextChannel, carch: ChannelArchiveStatus
    ):
        """Get the after time for the given text channel.

        Args:
            cobj (discord.TextChannel): _description_
        """
        if self.lazy:
            timev = carch.latest_archive_time
            return {"limit": self.collect_limit, "after": timev, "oldest_first": True}
        lasttime = (
            None
            if cobj.last_message_id is None
            else discord.utils.snowflake_time(cobj.last_message_id)
        )
        timev = self.last_stored_time
        if lasttime and timev:
            if lasttime < timev:
                gui.gprint(f"probably don't need to archive {cobj.name}")
                return "skip"

        await carch.get_first_and_last(cobj)
        if carch.first_message_time is not None:
            if carch.first_message_time > self.last_stored_time:
                # print("TOO BIG.")
                timev = self.last_stored_time  # carch.first_message_time
        else:
            timev = None
        return {"after": timev, "oldest_first": True, "limit": 100000}

    async def edit_mess(self, pre="", cname="", seconds=15):
        """Edits the status message to update the progress of the archival process.

        Args:
            pre: any prefix message.
            cname: current channel name.
        """
        place = f"{self.total_archived} messages collected in total.\n"
        current_index = f"{self.channel_spot}/{self.channel_count}"
        text = f"{place} \n On channel {current_index},\n {cname},\n Please wait. <a:SquareLoading:1143238358303264798>"
        emb = discord.Embed(description=text, color=self.server_color)
        emb.add_field(
            name=f"Server Channels {'remaining' if self.lazy else ''}",
            value=self.channel_count,
            inline=True,
        )
        emb.add_field(name="Currently Indexed", value=current_index, inline=True)
        emb.add_field(
            name=f"Total Messages archived{' this session' if self.lazy else ''}.",
            value=self.total_archived,
        )
        if self.lazy:
            emb.add_field(
                name="Current Unarchived Message Time Span",
                value=ChannelArchiveStatus.get_total_unarchived_time(
                    self.profile.server_id
                ),
            )
        (await self.status_mess.editw(min_seconds=seconds, content=text, embed=emb),)


async def iter_hist_messages(
    cobj: discord.TextChannel, actx: ArchiveContext
) -> Tuple[List[discord.Message], bool, int]:
    """
    This method asynchronously iterates over the historical messages in a given discord text channel and archives them based on
    the context of the archive. The archive context determines things like the time of the last stored message, whether or not to
    update the archive, and other operational parameters.

    Parameters:
    cobj (discord.TextChannel): The discord text channel to archive.
    actx (ArchiveContext): The context within which to perform the archive operation.

    Returns:
    list: A list of messages to be archived.
    """
    messages = []
    mlen = 0
    carch = ChannelArchiveStatus.get_by_tc(cobj)
    timev = await actx.get_first_time(cobj, carch)
    if timev == "skip":
        return [], False, 0
    count = 0
    lastmess = cobj.last_message_id
    lasttime = (
        discord.utils.snowflake_time(cobj.last_message_id)
        if cobj.last_message_id
        else None
    )
    # gui.gprint(cobj.name, " ", lastmess, " ", lasttime, " ", timev)
    reallasttime = None

    # return [];
    async for thisMessage in cobj.history(**timev):
        # if(thisMessage.created_at<=actx.last_stored_time and actx.update): break
        add_check = actx.evaluate_add(thisMessage)
        reallasttime = thisMessage.id
        count = count + 1
        if add_check:
            thisMessage.content = thisMessage.clean_content
            thisMessage.content = remove_lines_starting_with_gt(thisMessage.content)
            actx.alter_latest_time(thisMessage.created_at.timestamp())
            actx.character_len += len(thisMessage.content)
            messages.append(thisMessage)
            carch.increment(thisMessage.created_at)
            actx.total_archived += 1
            mlen += 1
        else:
            actx.total_ignored += 1
            gui.gprint(actx.total_ignored)
        if len(messages) % BATCH_SIZE == 0 and len(messages) > 0:
            hmes = await HistoryMakers.get_history_message_list(messages)
            messages = []
        if mlen % 200 == 0 and mlen > 0:
            await asyncio.sleep(1)
            await actx.edit_mess(cname=cobj.name)
            # await edittime.invoke_if_time(content=f"{mlen} messages so far in this channel, this may take a moment.   \n On channel {chancount}/{chanlen},\n {cobj.name},\n gathered <a:SquareLoading:1143238358303264798>.  This will take a while...")
            # await statusMess.updatew(f"{mlen} messages so far in this channel, this may take a moment.   \n On channel {chancount}/{chanlen},\n {cobj.name},\n gathered <a:SquareLoading:1143238358303264798>.  This will take a while...")
    if messages:
        hmes = await HistoryMakers.get_history_message_list(messages)
        messages = []
    if reallasttime:
        gui.dprint(reallasttime, "vs ", lastmess, " ", lasttime, " ", timev)
    else:
        gui.gprint(f"Did not need to archive {cobj.name}")
    actx.bot.database.commit()
    return messages, mlen > 0, count


async def collect_server_history_lazy(ctx: commands.Context, statmess=None, **kwargs):
    # Get at most LAZYGRAB_LIMIT messages from all channels in guild
    bot = ctx.bot
    channel = ctx.message.channel
    guild = channel.guild
    guildid = guild.id
    profile = ServerArchiveProfile.get_or_new(guildid)

    messages = []
    if statmess == None:
        statusMessToEdit = await channel.send(
            "I'm getting everything in the given RP channels, this may take a moment!"
        )

        statmess = StatusEditMessage(statusMessToEdit, ctx)
    time = profile.last_archive_time
    gui.dprint(time)
    # await channel.send("Starting at time:{}".format(time.strftime("%B %d, %Y %I:%M:%S %p")))

    if time:
        time = time.timestamp()
    if time == None:
        time = 1431518400
    last_time = datetime.fromtimestamp(time, timezone.utc)
    new_last_time = last_time.timestamp()

    # await channel.send("Starting at time:{}".format(last_time.strftime("%B %d, %Y %I:%M:%S %p")))

    chanlen = len(guild.text_channels)

    channels = ChannelArchiveStatus.get_all(guildid, outdated=True)

    arch_ctx = ArchiveContext(
        bot=bot,
        profile=profile,
        status_mess=statmess,
        last_stored_time=last_time,
        latest_time=new_last_time,
        channel_count=len(channels),
        lazy=True,
        **kwargs,
    )

    grabstat = False
    gui.gprint(len(channels))
    for c in channels:
        gui.print(c)

        arch_ctx.channel_spot += 1

        channel = guild.get_channel_or_thread(c.channel_id)
        if (not channel) and (c.thread_parent_id is not None):
            try:
                channel = await guild.fetch_channel(c.channel_id)
            except (
                discord.errors.InvalidData,
                discord.errors.Forbidden,
                discord.errors.NotFound,
            ) as e:
                await bot.send_error(e, "ex", True)
                ChannelArchiveStatus.delete_channel_by_id(c.channel_id)
        if channel:
            await arch_ctx.edit_mess(cname=channel.name, seconds=0)
            gui.gprint("Channel", channel)
            mes, have, count = await iter_hist_messages(channel, arch_ctx)
            grabstat = grabstat or have

    bot.database.commit()
    # await statmess.delete()
    return grabstat, statmess


async def setup_lazy_grab(ctx, **kwargs):
    # Collect from desired channels to a point.
    bot = ctx.bot
    channel = ctx.message.channel
    guild = channel.guild
    guildid = guild.id
    profile = ServerArchiveProfile.get_or_new(guildid)
    statusMessToEdit = await channel.send("Counting up channels.")
    statmess = StatusEditMessage(statusMessToEdit, ctx)
    chanlen = len(guild.text_channels)

    arch_ctx = ArchiveContext(
        bot=bot,
        profile=profile,
        status_mess=statmess,
        last_stored_time=None,
        latest_time=None,
        channel_count=chanlen,
        **kwargs,
    )

    current_channel_count, total_channels = 0, 0
    current_channel_every = max(chanlen // 50, 1)

    # Get all archivable channels.
    chantups = []
    chantups.extend(("forum", chan) for chan in guild.forums)
    chantups.extend(("textchan", chan) for chan in guild.text_channels)
    for tup, chan in chantups:
        total_channels += 1
        if (
            profile.has_channel(chan.id) == False
            and chan.permissions_for(guild.me).view_channel == True
            and chan.permissions_for(guild.me).read_message_history == True
        ):
            if chan.category:
                if profile.has_channel(chan.category.id) == True:
                    continue
            threads = chan.threads
            archived = []
            async for thread in chan.archived_threads():
                archived.append(thread)
            threads = threads + archived
            for thread in threads:
                tarch = ChannelArchiveStatus.get_by_tc(thread)
                await tarch.get_first_and_last(thread, force=True)
            if tup == "textchan":
                carch = ChannelArchiveStatus.get_by_tc(chan)
                await carch.get_first_and_last(chan, force=True)
            bar = futil.progress_bar(total_channels, chanlen, width=8)
            await statmess.editw(min_seconds=3, content=f"{bar}")
            if current_channel_count > current_channel_every:
                await asyncio.sleep(1)
                # await edittime.invoke_if_time()
                current_channel_count = 0
    bar = futil.progress_bar(total_channels, chanlen, width=8)
    await statmess.editw(0, content=bar)


async def collect_server_history(ctx, **kwargs):
    # Collect from desired channels to a point.
    bot = ctx.bot
    channel = ctx.message.channel
    guild = channel.guild
    guildid = guild.id
    profile = ServerArchiveProfile.get_or_new(guildid)

    messages = []
    statusMessToEdit = await channel.send(
        "I'm counting up the given RP channels, this may take a moment!"
    )

    statmess = StatusEditMessage(statusMessToEdit, ctx)
    time = profile.last_archive_time
    gui.dprint(time)
    if time:
        # await channel.send(            "Starting at time:{}".format(time.strftime("%B %d, %Y %I:%M:%S %p"))        )
        time = time.timestamp()
    if time is None:
        time = 1431518400
    last_time = datetime.fromtimestamp(time, timezone.utc)
    new_last_time = last_time.timestamp()

    # await channel.send(        "Starting at time:{}".format(last_time.strftime("%B %d, %Y %I:%M:%S %p"))    )
    chantups = []
    chantups.extend(("forum", chan) for chan in guild.forums)

    chantups.extend(("textchan", chan) for chan in guild.text_channels)
    chanlen = len(chantups)
    # hex = await get_server_icon_color(ctx.guild)
    arch_ctx = ArchiveContext(
        bot=bot,
        profile=profile,
        status_mess=statmess,
        last_stored_time=last_time,
        latest_time=new_last_time,
        channel_count=chanlen,
        # color=hex,
        **kwargs,
    )

    current_channel_count = 0
    current_channel_every = 50
    totalcharlen = 0
    mode = profile.get_ignore_mode()
    await arch_ctx.edit_mess(seconds=0)
    unarchive_chain = True
    for tup, chan in chantups:
        arch_ctx.channel_spot += 1
        doarchive = should_archive_channel(mode, chan, profile, guild)

        if doarchive:
            threads = chan.threads
            if unarchive_chain:
                await arch_ctx.edit_mess("", chan.name, seconds=0)
                unarchive_chain = False

            lastmessage_str = f"{tup}, {chan.name}: {chan.last_message_id}"
            gui.gprint(lastmessage_str)
            archived = []
            async for thread in chan.archived_threads():
                archived.append(thread)
            threads = threads + archived
            for thread in threads:
                lastmessage_str = f"{tup}, {chan.name}, {thread.name}: {chan.last_message_id}, {thread.last_message_id}"
                gui.gprint(lastmessage_str)
                mess, _, _ = await iter_hist_messages(thread, arch_ctx)
                messages = messages + mess
                current_channel_count += 1

            if tup == "textchan":
                chanmess, _, _ = await iter_hist_messages(chan, arch_ctx)
                # new_last_time=max(new_last_time,newtime)
                # ignored+=ign
                # totalcharlen+=charlen
                messages = messages + chanmess
                current_channel_count += 1

            await arch_ctx.edit_mess("", chan.name)
            if current_channel_count % current_channel_every == 0:
                await asyncio.sleep(1)
        else:
            unarchive_chain = True

    if statusMessToEdit != None:
        await statusMessToEdit.delete()
    bot.database.commit()
    return messages, arch_ctx.character_len, arch_ctx.latest_time


def check_channel(historychannel: discord.TextChannel) -> Tuple[bool, str]:
    """Check if the passed in history channel has the needed permissions."""
    permissions = historychannel.permissions_for(historychannel.guild.me)
    messagableperms = [
        "read_messages",
        "send_messages",
        "manage_messages",
        "manage_webhooks",
        "embed_links",
        "attach_files",
        "add_reactions",
        "external_emojis",
        "external_stickers",
    ]
    add = "."

    for p, v in permissions:
        if v:
            if p in messagableperms:
                messagableperms.remove(p)
    if len(messagableperms) > 0:
        missing = futil.permission_print(messagableperms)
        result = f"I am missing the following permissions for the specified log channel {historychannel.mention}:  {missing}\n  Please update my permissions for this channel."
        return False, result
    return True, "Needed permissions are set in this channel" + add
