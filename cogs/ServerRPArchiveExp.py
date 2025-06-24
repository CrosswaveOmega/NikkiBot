import gui
import discord
import asyncio

# import datetime
from datetime import datetime

from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands


from discord.app_commands import Choice

from database import ServerArchiveProfile
from .ArchiveSub import (
    ArchivedRPMessage,
)


class ToChoice(commands.Converter):
    async def convert(self, ctx, argument):
        if not ctx.interaction:
            if type(argument) == str:
                choice = Choice(name="fallback", value=argument)
                return choice
        else:
            return argument


def should_archive_channel(
    mode: int, chan: discord.TextChannel, profile, guild: discord.Guild
):
    chan_ignore = profile.has_channel(chan.id)
    cat_ignore = chan.category and profile.has_channel(chan.category.id)
    if not (
        chan.permissions_for(guild.me).view_channel
        and chan.permissions_for(guild.me).read_message_history
    ):
        return False, "NO PERMS"

    if mode == 0:
        return not chan_ignore and not cat_ignore, f"Mode {chan_ignore},{cat_ignore}"
    elif mode == 1:
        return chan_ignore, f"Mode {chan_ignore},{cat_ignore}"
    elif mode == 2:
        return cat_ignore and not bool(chan_ignore), f"Mode {chan_ignore},{cat_ignore}"

    return False, "No mode at all..."


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
    async def check_message_archive_ignore(self, ctx):
        chantups = []
        guild = ctx.guild
        if not guild:
            await ctx.send("Must be in guild")
        chantups.extend(("forum", chan) for chan in guild.forums)

        chantups.extend(("textchan", chan) for chan in guild.text_channels)

        profile = ServerArchiveProfile.get_or_new(guild.id)
        mode = profile.get_ignore_mode()
        await ctx.send(f"Archive mode  {mode}")
        for tup, chan in chantups:
            doarchive = should_archive_channel(mode, chan, profile, guild)
            await ctx.send(f"Can archive {chan.name} {doarchive}")

    @commands.command(extras={"guildtask": ["rp_history"]})
    async def summarize_day(self, ctx, daystr: str, endstr: str = None):
        from .ArchiveSub import (
            ArchivedRPMessage,
            ChannelArchiveStatus,
            ChannelSep,
            LazyContext,
            MessageTemplates,
            check_channel,
            lazy_archive,
            setup_lazy_grab,
        )
        from bot import (
            StatusEditMessage,
        )
        from datetime import timedelta

        """Create a calendar of all archived messages with dates in this channel."""
        bot = ctx.bot
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id
        if await ctx.bot.gptapi.check_oai(ctx):
            return

        def format_location_name(csep):
            # Replace dashes with spaces
            channel_name = csep.channel
            category = csep.category
            thread = csep.thread
            formatted_name = channel_name.replace("-", " ")

            # Capitalize the first letter
            formatted_name = formatted_name.capitalize()
            output = f"Location: {formatted_name}, {category}."
            if thread != None:
                output = f"{output}  {thread}"
            return output

        me = await ctx.channel.send(
            content=f"<a:LetWalk:1118184074239021209> Retrieving archived messages..."
        )
        mt = StatusEditMessage(me, ctx)
        datetime_object = datetime.strptime(
            f"{daystr} 00:00:00 +0000", "%Y-%m-%d %H:%M:%S %z"
        )
        datetime_object_end = datetime_object
        if endstr:
            datetime_object_end = datetime.strptime(
                f"{endstr} 00:00:00 +0000", "%Y-%m-%d %H:%M:%S %z"
            )

        script = ""
        count = ecount = mcount = 0
        ecount = 0
        await ctx.send("Starting gather.")

        for sep in ChannelSep.get_all_separators_on_dates(
            guildid, datetime_object, datetime_object_end
        ):
            ecount += 1
            await mt.editw(
                min_seconds=15,
                content=f"<a:LetWalk:1118184074239021209> Currently on Separator {ecount} ({sep.message_count}),message {mcount}.",
            )
            location = format_location_name(sep)

            script += "\n" + location + "\n"
            await asyncio.sleep(0.2)
            messages = sep.get_messages()
            await asyncio.sleep(0.5)
            for m in messages:
                count += 1
                mcount += 1
                await asyncio.sleep(0.1)
                if count > 5:
                    # To avoid blocking the asyncio loop.
                    await mt.editw(
                        min_seconds=15,
                        content=f"<a:LetWalk:1118184074239021209> Currently on Separator {ecount},message {mcount}.",
                    )

                    count = 0
                embed = m.get_embed()
                if m.content:
                    script = f"{script}\n {m.author}: {m.content}"
                elif embed:
                    embed = embed[0]
                    if embed.type == "rich":
                        embedscript = f"{embed.title}: {embed.description}"
                        script = f"{script}\n {m.author}: {embedscript}"

        # Save the script to a file
        filename = f"archive_{daystr}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(script)
            await ctx.send(f"Script saved as {filename}.")
        except Exception as e:
            await ctx.send(f"Failed to save script: {e}")

        # Send the file
        try:
            await ctx.send(file=discord.File(filename))
        except Exception as e:
            await ctx.send(f"Failed to send script file: {e}")


async def setup(bot):
    gui.dprint(__name__)
    # from .ArchiveSub import setup
    # await bot.load_extension(setup.__module__)
    await bot.add_cog(ServerRPArchiveExtra(bot))


async def teardown(bot):
    # from .ArchiveSub import setup
    # await bot.unload_extension(setup.__module__)
    await bot.remove_cog("ServerRPArchiveExtra")
