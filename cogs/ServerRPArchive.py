import asyncio
from collections import defaultdict

# import datetime
from datetime import datetime, timedelta
from typing import Union

import discord
from dateutil.rrule import MINUTELY, SU, WEEKLY, rrule
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

import gui
from bot import (
    Guild_Task_Functions,
    TC_Cog_Mixin,
    TCBot,
    TCGuildTask,
)
from database import DatabaseSingleton, ServerArchiveProfile
from utility import RRuleView
from utility import WebhookMessageWrapper as web
from utility import (
    formatutil,
    serverAdmin,
    serverOwner,
    urltomessage,
)
from utility.embed_paginator import pages_of_embeds

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


class ToChoice(commands.Converter):
    async def convert(self, ctx, argument):
        if not ctx.interaction:
            gui.dprint(type(argument))
            if type(argument) == str:
                choice = Choice(name="fallback", value=argument)
                return choice
        else:
            return argument


class ServerRPArchive(commands.Cog, TC_Cog_Mixin):
    """This class is intended for Discord RP servers that use Tupperbox or another proxy application.."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        self.loadlock = asyncio.Lock()
        self.helptext = """This cog is intended for Discord RP servers that use Tupperbox or another proxy bot.  It condences all RP messages (messages sent with a proxy bot such as Tupperbox) sent across a server (ignoring channels when needed) into a single server specific channel, while grouping them into blocks via a specialized algorithm based on the time and category,channel, and thread(if needed) of each rp message.
        
        Please note, in order to work, this command **saves a copy of every archived RP message into a local database.**  
        
        ***Only messages sent by bots and webhooks will be archived!***

        Get started by utilizing the archive_setup family of commands to configure your archive channel and add your ignore channels.
        """
        self.guild_cache = defaultdict(int)
        self.guild_db_cache = defaultdict(lambda: None)

        Guild_Task_Functions.add_task_function("COMPILE", self.gtask_compile)

        Guild_Task_Functions.add_task_function("LAZYARCHIVE", self.gtask_lazy)

    def cog_unload(self):
        # Remove the task function.
        Guild_Task_Functions.remove_task_function("COMPILE")
        Guild_Task_Functions.remove_task_function("LAZYARCHIVE")
        pass

    def server_profile_field_ext(self, guild: discord.Guild):
        """
        Create a dictionary representing the automatic archive status for
        this server.
        """
        profile = ServerArchiveProfile.get(guild.id)
        if not profile:
            return None
        last_date = aid = ""
        hist_channel = profile.history_channel_id
        if profile.last_archive_time:
            timestamped = profile.last_archive_time.timestamp()
            last_date = f"<t:{int(timestamped)}:f>"
        if hist_channel:
            aid = f"<#{hist_channel}>"
        if aid:
            clist = profile.count_channels()
            value = f"Archive Channel: {aid}\n"
            if last_date:
                value += f"Last Run: {last_date}\n"
            value += f"Ignored Channels: {clist}\n"

            autoentry = TCGuildTask.get(guild.id, "COMPILE")
            if autoentry:
                res = autoentry.get_status_desc()
                if res:
                    value += res
            field = {"name": "Server RP Archive", "value": value}
            return field
        return None

    async def gtask_lazy(self, source_message=None):
        """
        This is the guild task for the Lazy Archive Mode, intended for massive servers with
        millions of messages.
        Lazy Archive Mode operates in phases.
        """
        if not source_message:
            return None
        context = await self.bot.get_context(source_message)
        try:
            result = await lazy_archive(self, context)
            if result == False:
                gui.gprint("Done.")
                TCGuildTask.get(context.guild.id, "LAZYARCHIVE").remove_after = True
            await source_message.delete()
        except Exception as e:
            er = MessageTemplates.get_error_embed(
                title="Error with AUTO", description=f"{str(e)}"
            )
            await source_message.channel.send(embed=er)
            raise e

    async def gtask_compile(self, source_message=None):
        """
        Guild task for the scheduled
        """
        if not source_message:
            return None
        context = await self.bot.get_context(source_message)
        # await context.channel.send("Greetings from GTASK.")
        try:
            await context.invoke(
                self.bot.get_command("compile_archive"), send_all_clear_message=False
            )
        except Exception as e:
            er = MessageTemplates.get_error_embed(
                title="Error with AUTO", description=f"{str(e)}"
            )
            await source_message.channel.send(embed=er)
            raise e

    @commands.command(hidden=True)
    async def channelcount(self, ctx: commands.Context):
        """
        Get a count of all channels in your server.
        """
        guild = ctx.message.channel.guild
        acount, ccount, catcount = 0, 0, 0
        for chan in guild.channels:
            acount += 1
            if chan.type == discord.ChannelType.text:
                ccount += 1
            if chan.type == discord.ChannelType.category:
                catcount += 1
        await ctx.send(
            "```allchannels:{}, \n Total text channels: {}, \n categories: {}.```".format(
                acount, ccount, catcount
            )
        )

    @app_commands.command(
        name="compile_sanity_check",
        description="ensure that the needed permissions for the auto channel are set",
    )
    async def sanity_check(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        bot = ctx.bot
        guild = ctx.guild
        task_name = "COMPILE"
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You don't have permission to use this command.."
            )
            return False
        old = TCGuildTask.get(guild.id, task_name)
        if old:
            autochannel = bot.get_channel(old.target_channel_id)
            # check if the passed in autochannel meets the standards.
            passok, statusmessage = Guild_Task_Functions.check_auto_channel(autochannel)
            if not passok:
                await MessageTemplates.server_archive_message(
                    ctx, statusmessage, ephemeral=True
                )
            else:
                await MessageTemplates.server_archive_message(
                    ctx, "Everything should be a-ok"
                )
        else:
            await MessageTemplates.server_archive_message(
                ctx, "You never set up an auto channel!"
            )

    @commands.command(enabled=False, hidden=True)
    async def ignoreusers(self, ctx):
        """
        WORK IN PROGRESS: IGNORE ARCHIVING FROM THESE USERS.
        """
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id

        if not (serverOwner(ctx) or serverAdmin(ctx)):
            return False

        profile = ServerArchiveProfile.get_or_new(guildid)
        chanment = ctx.message.mentions
        if len(chanment) >= 1:
            for user in chanment:
                gui.gprint(user.name)
                profile.add_user_to_list(user.id)
        self.guild_db_cache[str(ctx.guild.id)] = profile
        self.bot.database.commit()

    @commands.hybrid_group(fallback="view")
    @app_commands.default_permissions(manage_messages=True, manage_channels=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, manage_channels=True)
    async def archive_setup(self, ctx):
        """This family of commands is for setting up your server archive."""
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id
        await MessageTemplates.server_archive_message(
            ctx, "Here is your server's archive data."
        )

    @archive_setup.command(
        name="help_manual", brief="Learn how to use the archive system"
    )
    async def archive_manual(self, ctx):
        """This family of commands is for setting up your server archive."""
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id
        pages = await MessageTemplates.get_manual_list(ctx, "nikki_archive_system.json")
        await pages_of_embeds(ctx, pages, ephemeral=True)

    @archive_setup.command(
        name="set_archive_channel", brief="set a desired Archive Channel."
    )
    @app_commands.describe(chanment="The new archive channel you want to set.")
    async def setArchiveChannel(
        self, ctx, chanment: discord.TextChannel
    ):  # Add ignore.
        """Use this command to set an Archive Channel."""

        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await ctx.send("You do not have permission to use this command.")
            return False

        profile = ServerArchiveProfile.get_or_new(guildid)
        gui.gprint(profile)
        passok, statusmessage = check_channel(chanment)
        if not passok:
            await MessageTemplates.server_archive_message(ctx, statusmessage)
            return
        if profile.history_channel_id:
            choice, mes = await MessageTemplates.confirm(
                ctx, "Are you sure you want to change your archive channel?"
            )
            await mes.delete()
            if not choice:
                await MessageTemplates.server_archive_message(
                    ctx, "The Server Archive Channel has been set."
                )
        newchan_id = chanment.id
        profile.add_or_update(guildid, history_channel_id=newchan_id)
        self.guild_db_cache[str(ctx.guild.id)] = profile
        bot.database.commit()

        await MessageTemplates.server_archive_message(
            ctx, "The Server Archive Channel has been set."
        )

    @archive_setup.command(
        name="enable_auto",
        brief="archive ",
    )
    @app_commands.describe(
        autochannel="a channel where the command will run.  not same thing as the archive_channel!"
    )
    async def enable_auto(self, ctx, autochannel: discord.TextChannel):
        """Add an automatic task."""
        bot = ctx.bot
        guild = ctx.guild
        task_name = "COMPILE"
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You don't have permission to use this command.."
            )
            return False

        # check if the passed in autochannel meets the standards.
        passok, statusmessage = Guild_Task_Functions.check_auto_channel(autochannel)

        if not passok:
            await MessageTemplates.server_archive_message(ctx, statusmessage)
            return

        prof = ServerArchiveProfile.get(server_id=guild.id)
        if not prof:
            await MessageTemplates.server_archive_message(
                ctx, "...you've gotta set up the archive first..."
            )
            return
        if autochannel.id == prof.history_channel_id:
            result = "this should not be the same channel as the archive channel.  Specify a different channel such as a bot spam channel."
            await MessageTemplates.server_archive_message(ctx, result)
            return

        old = TCGuildTask.get(guild.id, task_name)
        if not old:
            message = await autochannel.send(
                f"**ATTEMPTING SET UP OF AUTO COMMAND {task_name}**"
            )
            myurl = message.jump_url
            start_date = datetime(2023, 1, 1, 15, 0)
            nowd = datetime.now() + timedelta((6 - datetime.now().weekday()) % 7)
            st = datetime(nowd.year, nowd.month, nowd.day, 15, 0)
            robj = rrule(freq=WEEKLY, byweekday=SU, dtstart=start_date)

            new = TCGuildTask.add_guild_task(guild.id, task_name, message, robj)
            new.to_task(bot)

            result = f"The automatic archive system is set up for <#{autochannel.id}>.  See you on Sunday at 3pm est."
            await MessageTemplates.server_archive_message(ctx, result)
        else:
            old.target_channel_id = autochannel.id

            message = await autochannel.send("**ALTERING AUTO CHANNEL...**")
            old.target_message_url = message.jump_url
            self.bot.database.commit()
            result = f"Changed the auto log channel to <#{autochannel.id}>"
            await MessageTemplates.server_archive_message(ctx, result)

    @archive_setup.command(
        name="updatenextauto", brief="change the next automatic time."
    )
    @app_commands.describe(newtime="Minutes from now.")
    async def updatenextauto(self, ctx, newtime: int):
        """set a new time for the next automatic task."""
        bot = ctx.bot
        guild = ctx.guild
        task_name = "COMPILE"
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You don't have permission to use this command.."
            )
            return False

        old = TCGuildTask.get(guild.id, task_name)
        if old:
            old.change_next_run(self.bot, datetime.now() + timedelta(minutes=newtime))
            result = "Time has changed to newtime."
            await MessageTemplates.server_archive_message(ctx, result)
        else:
            await MessageTemplates.server_archive_message(
                ctx, "I can't find the guild task."
            )

    @archive_setup.command(
        name="change_auto_interval", brief="change how often I archive the server."
    )
    async def change_auto_interval(self, ctx):
        """set a new time for the next automatic task."""
        bot = ctx.bot
        guild = ctx.guild
        task_name = "COMPILE"
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You don't have permission to use this command.."
            )
            return False

        old = TCGuildTask.get(guild.id, task_name)
        if old:
            view = RRuleView(ctx.author)
            message = await ctx.send(
                "Understood!  Please use the view below to change the recurrence rules for archiving.\n"
                + "Think of it like setting up a repeating event on your iPhone/Android.",
                view=view,
                ephemeral=True,
            )
            await asyncio.sleep(2)
            await view.wait()
            if view.value == "TIMEOUT":
                await ctx.send("Sorry, you hit a timeout, try again later.")
            elif view.value:
                await ctx.send(f"`{str(view.value)}`")
                old.change_rrule(self.bot, view.value)
                desc, sent = formatutil.explain_rrule(view.value)
                result = f"I've changed the recurrence settings! \n {sent}"
                await MessageTemplates.server_archive_message(ctx, result)
            else:
                await ctx.send("I see.  I'll stop.")
            # await message.delete()

        else:
            await MessageTemplates.server_archive_message(
                ctx, "I can't find the guild task."
            )

    @archive_setup.command(
        name="disable_auto_archive", brief="stop automatically archiving the server"
    )
    async def disable_auto(self, ctx):
        """remove an automatic task."""
        bot = ctx.bot
        guild = ctx.guild
        task_name = "COMPILE"
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You don't have permission to use this command."
            )
            return False
        message = await ctx.send("Target Message.")
        myurl = message.jump_url
        new = TCGuildTask.remove_guild_task(guild.id, task_name)

        result = "the auto archive has been disabled."
        await MessageTemplates.server_archive_message(ctx, result)

    @archive_setup.command(
        name="setup_new_archive_channel",
        brief="the bot will create a new archive channel with set permissions.",
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True)
    async def setup_new_archive_channel_with_roles(self, ctx):  # Add ignore.
        """Want to set up a new archive channel automatically?
        Use this command and a new archive channel will be created in this server with a historian role that only allows the bot user from posting inside the channel.

        The bot must have **Manage Channels** and **Manage Roles** to use this command.
        """

        bot = ctx.bot
        auth = ctx.message.author
        channel: discord.TextChannel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            result = "You lack permissions to use this command."
            await MessageTemplates.server_archive_message(ctx, result)
            return

        my_permissions = guild.me.guild_permissions

        permission_check_string = ""
        if not my_permissions.manage_roles:
            permission_check_string = "I don't have the **'Manage Roles'** permission needed to create a 'Historian' role."
        if not my_permissions.manage_channels:
            permission_check_string = "I can't make you an archive channel without the **'Manage Channels'** permission."
        if not my_permissions.manage_roles and not my_permissions.manage_channels:
            permission_check_string = "To create an archive channel and set the proper permissions, I need the **'Manage Roles'** and **'Manage Channels'** permissions."

        if permission_check_string:
            result = f"{permission_check_string}\n  Please update my permissions in Server Settings.  \n*You may remove the permissions after this command finishes.*"
            await MessageTemplates.server_archive_message(ctx, result)
            return

        profile = ServerArchiveProfile.get_or_new(guildid)

        # Check if history channel already exists.
        if profile.history_channel_id:
            if guild.get_channel(profile.history_channel_id):
                result = "You already have a set archive channel, no reason for me to make a new one."
                await MessageTemplates.server_archive_message(ctx, result)
                return

        # create Historian role and give it to bot
        historian_role = discord.utils.get(guild.roles, name="Historian")
        if historian_role is None:
            historian_role = await guild.create_role(name="Historian")

        if historian_role not in guild.me.roles:
            await guild.me.add_roles(historian_role)

        # create new channel and set permissions for Historian role
        category = channel.category
        channel_name = "history-archive"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False
            ),  # disallow sending messages for @everyone role
            historian_role: discord.PermissionOverwrite(
                send_messages=True
            ),  # allow sending messages for Historian role
        }
        new_channel = await guild.create_text_channel(
            name=channel_name, category=category, overwrites=overwrites
        )

        profile.add_or_update(guildid, history_channel_id=new_channel.id)
        self.guild_db_cache[str(ctx.guild.id)] = profile
        bot.database.commit()

        await MessageTemplates.server_archive_message(
            ctx, "Created and set a new Archive channel for this server."
        )

    @archive_setup.command(
        name="ignore_category",
        brief="add or remove a category to/from this server's ignore list.",
    )
    @app_commands.choices(
        mode=[  # param name
            Choice(name="Add category to ignore list", value="add"),
            Choice(name="Remove category from ignore list", value="remove"),
        ]
    )
    @app_commands.describe(
        mode="if specified category should be ignored or listened to.",
        cat="Name of category to ignore",
    )
    async def ignore_category(
        self, ctx: commands.Context, mode: ToChoice, cat: discord.CategoryChannel
    ):
        """
        Add or remove mentioned categories to/from this server's ignore list. Ignored channels will not be archived.
        """
        bot = ctx.bot
        thismessage = ctx.message
        auth = ctx.message.author
        channel = ctx.message.channel

        guild = channel.guild
        guildid = guild.id

        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You do not have permission to use this command."
            )
            return False

        profile = ServerArchiveProfile.get_or_new(guildid)

        if mode == "add":
            if profile.has_channel(cat.id):
                await MessageTemplates.server_archive_message(
                    ctx, f"You are already ignoring category `{cat.name}`."
                )
                return
            profile.add_channel(cat.id)
            message = f"Added category `{cat.name}` to my ignore list.  All messages in its {len(cat.channels)} channels will be ignored while archiving."
        elif mode == "remove":
            if not profile.has_channel(cat.id):
                await MessageTemplates.server_archive_message(
                    ctx, f"I'm not ignoring category `{cat.name}`."
                )
                return
            profile.remove_channel(cat.id)
            message = f"Removed category `{cat.name}` from my ignore list.  All messages in its {len(cat.channels)} channels will no longer be ignored while archiving."

        self.bot.database.commit()
        self.guild_db_cache[str(ctx.guild.id)] = profile
        await MessageTemplates.server_archive_message(ctx, message)

    @archive_setup.command(
        name="ignore_channel",
        brief="add or remove a single channel to/from this server's ignore list.",
    )
    @app_commands.choices(
        mode=[  # param name
            Choice(name="Add channel to ignore list", value="add"),
            Choice(name="Remove channel from ignore list", value="remove"),
        ]
    )
    @app_commands.describe(
        mode="if specified channel should be ignored or listened to.",
        channel="Name of channel to ignore",
    )
    async def ignore_channel(
        self,
        ctx: commands.Context,
        mode: ToChoice,
        channel: Union[discord.TextChannel, discord.ForumChannel],
    ):  # Add ignore.
        """
        Add or remove mentioned channels to/from this server's ignore list. Ignored channels will not be archived.
        """
        bot = ctx.bot
        thismessage = ctx.message
        auth = ctx.message.author

        guild = ctx.guild
        guildid = guild.id
        # await ctx.send(f"{cat.id},{cat.name},{len(cat.channels)}")
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You do not have permission to use this command."
            )
            return False
        profile = ServerArchiveProfile.get_or_new(guildid)
        if mode == "add":
            if profile.has_channel(channel.id):
                await MessageTemplates.server_archive_message(
                    ctx, f"You are already ignoring channel `{channel.name}`."
                )
                return
            profile.add_channel(channel.id)

            self.bot.database.commit()
            self.guild_db_cache[str(ctx.guild.id)] = profile
            await MessageTemplates.server_archive_message(
                ctx,
                f"Added channel `{channel.name}` to my ignore list.",
            )
        if mode == "remove":
            if profile.has_channel(channel.id):
                profile.remove_channel(channel.id)

                self.bot.database.commit()
                self.guild_db_cache[str(ctx.guild.id)] = profile
                await MessageTemplates.server_archive_message(
                    ctx,
                    f"Removed channel `{channel.name}` from my ignore list.",
                )
                return

            await MessageTemplates.server_archive_message(
                ctx, f"I'm not ignoring channel `{channel.name}`."
            )

    @archive_setup.command(
        name="ignore_many_channels",
        brief="Add or remove mentioned channels to/from this server's ignore list.",
    )
    @app_commands.choices(
        mode=[
            Choice(name="Add channels to ignore list", value="add"),
            Choice(name="Remove channels from ignore list", value="remove"),
        ]
    )
    @app_commands.describe(
        mode="if specified channels should be ignored or listened to."
    )
    async def ignore_many_channels(self, ctx, mode: ToChoice):
        """
        Add or remove mentioned channels to/from this server's ignore list.
        """
        bot = ctx.bot
        thismessage = ctx.message
        auth = ctx.message.author
        channel = ctx.message.channel

        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You do not have permission to use this command."
            )
            return False

        def check(m):
            return m.author == auth and m.channel == channel

        if ctx.interaction:
            await ctx.send(
                f"Due to app command limitations, please specify all the channels you want to {'ignore' if mode == 'add' else 'stop ignoring'} in another message below, you have {formatutil.get_time_since_delta(timedelta(minutes=15))}."
            )
            try:
                msg = await bot.wait_for("message", timeout=60.0 * 15, check=check)
                thismessage = msg
            except asyncio.TimeoutError:
                await ctx.send("You took way too long.")
                return

        guild = channel.guild
        guildid = guild.id

        profile = ServerArchiveProfile.get_or_new(guildid)
        chanment = thismessage.channel_mentions
        if len(chanment) >= 1:
            for chan in chanment:
                if mode == "add":
                    profile.add_channel(chan.id)
                elif mode == "remove":
                    profile.remove_channel(chan.id)
        else:
            await MessageTemplates.server_archive_message(
                ctx, "You mentioned no channels."
            )
            return

        self.bot.database.commit()
        self.guild_db_cache[str(ctx.guild.id)] = profile
        await MessageTemplates.server_archive_message(
            ctx,
            f"{'Added' if mode == 'add' else 'Removed'} channels {'to' if mode == 'add' else 'from'} my ignore list. Any messages in these channels will {'be ignored' if mode == 'add' else 'no longer be ignored'} while archiving.",
        )

    @archive_setup.command(
        name="remove_deleted_channels",
        brief="removes channels from this server's ignore list that have been deleted.",
    )
    async def remove_deleted_channels(self, ctx):
        """
        Removes deleted channels from this server's ignore list.
        """

        guild = ctx.guild
        guildid = guild.id

        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(
                ctx, "You do not have permission to use this command."
            )
            return False
        profile = ServerArchiveProfile.get_or_new(guildid)
        channels = profile.list_channels()
        removed = []
        for channel in channels:
            if guild.get_channel(channel) == None:
                profile.remove_channel(channel)
                removed.append(channel)

        self.guild_db_cache[str(ctx.guild.id)] = profile
        self.bot.database.commit()
        await MessageTemplates.server_archive_message(
            ctx, f"Removed {len(removed)} deleted channels from my ignore list."
        )

    @archive_setup.command(
        name="set_scope",
        description="Configure the archive scope, the bot will archive messages only if the authors are in this scope.",
    )
    @app_commands.choices(
        scope=[  # param name
            Choice(name="Only Archive Bot Messages", value="ws"),
            Choice(name="Only Archive User Messages", value="user"),
            Choice(name="Archive All Messages", value="both"),
        ]
    )
    async def set_scope(self, ctx, scope: ToChoice):
        if ctx.guild:
            scopes = {
                "ws": "Bots and Webhook Messages Only",
                "user": "User Messages Only",
                "both": "Every message, reguardless of sender",
            }
            gui.dprint(scope)
            if not (serverOwner(ctx)):
                await MessageTemplates.server_archive_message(
                    ctx, "Only the server owner may use this command."
                )
                return False
            profile = ServerArchiveProfile.get_or_new(ctx.guild.id)
            oldscope = profile.archive_scope
            if not oldscope:
                oldscope = "ws"
            gui.dprint(oldscope)
            if scope not in ["ws", "user", "both"]:
                await ctx.send(f"The specified scope {scope} is invalid.")
            steps = [
                "# Warning! \n  Changing the archive scope can cause issues if you already have messages within my log!"
                + "\nAre you sure about this?",
                f"You are?  Alright, so just to be clear, you want me \nto begin archiving **{scopes[scope]}**"
                + f"instead of archiving **{scopes[oldscope]}.**\nIs that correct?",
                "I need one final confirmation before I change the setting.  \n You are sure you want to change the archive scope?",
            ]
            for r in steps:
                confirm, mes = await MessageTemplates.confirm(ctx, r, ephemeral=False)

                if not confirm:
                    await MessageTemplates.server_archive_message(
                        ctx, "Very well, scope changed aborted.", ephemeral=True
                    )
                    return
                await mes.delete()

            profile.update(archive_scope=scope)
            self.guild_db_cache[str(ctx.guild.id)] = profile
            await MessageTemplates.server_archive_message(
                ctx, "Ok then, I've changed the archive scope.", ephemeral=True
            )
        else:
            await ctx.send("guild only.")

    @archive_setup.command(
        name="set_ignore_mode",
        description="Configure the ignore mode, which determines how specified channels are handled.",
    )
    @app_commands.choices(
        mode=[  # param name
            Choice(name="Ignore Specified Channels", value=0),
            Choice(name="Only Archive Specified Channels", value=1),
            Choice(name="Only Archive Specified Categories", value=2),
        ]
    )
    async def set_ignore_mode(self, ctx, mode: int):
        if ctx.guild:
            modes = {
                0: "Ignore Specified Channels",
                1: "Only Archive Specified Channels",
                2: "Only Archive Specified Categories, Ignore Specified Channels",
            }
            gui.dprint(mode)
            if not (serverOwner(ctx) or serverAdmin(ctx)):
                await MessageTemplates.server_archive_message(
                    ctx, "Only the server owner may use this command."
                )
                return False

            profile = ServerArchiveProfile.get_or_new(ctx.guild.id)
            old_mode = profile.ignore_mode if profile.ignore_mode is not None else 0
            gui.dprint(old_mode)

            if mode not in [0, 1, 2]:
                await ctx.send(f"The specified mode {mode} is invalid.")
                return

            steps = [
                "# Warning! \n Changing the ignore mode can affect existing archive behavior!"
                "\nAre you sure about this?",
                f"You are? Alright, so just to be clear, you want me \n"
                f"to switch to **{modes[mode]}** instead of **{modes[old_mode]}**.\nIs that correct?",
                "I need one final confirmation before I change the setting."
                "\nAre you absolutely sure?",
            ]

            for r in steps:
                confirm, mes = await MessageTemplates.confirm(ctx, r, ephemeral=False)

                if not confirm:
                    await MessageTemplates.server_archive_message(
                        ctx, "Very well, mode change aborted.", ephemeral=True
                    )
                    return
                await mes.delete()

            profile.update(ignore_mode=mode)
            self.guild_db_cache[str(ctx.guild.id)] = profile
            await MessageTemplates.server_archive_message(
                ctx, "Ok then, I've changed the ignore mode.", ephemeral=True
            )
        else:
            await ctx.send("Guild only.")

    @archive_setup.command(
        name="set_active_collect",
        description="Nikki can store rp messages in her database when they are sent, use this to enable that setting.",
    )
    @app_commands.describe(
        mode="True if Nikki should store RP messages in her database when recieved, False otherwise."
    )
    async def set_active(self, ctx, mode: bool = False):
        if ctx.guild:
            profile = ServerArchiveProfile.get_or_new(ctx.guild.id)
            oldscope = profile.archive_dynamic
            if oldscope == mode:
                await ctx.send("This is the same as my current setting.")
            steps = [
                "# Warning! \n  **Before** you use this command, please make sure you've used my `add_ignore_channels` command on all channels you don't want me reposting into my log!"
                + "\n Did you check this?"
            ]
            for r in steps:
                confirm, mes = await MessageTemplates.confirm(ctx, r, ephemeral=False)

                if not confirm:
                    await MessageTemplates.server_archive_message(
                        ctx, "Very well, scope changed aborted.", ephemeral=True
                    )
                    return
                await mes.delete()

            profile.update(archive_dynamic=mode)
            self.guild_db_cache[str(ctx.guild.id)] = profile
            if mode == True:
                self.guild_cache[str(ctx.guild.id)] = 2
            else:
                self.guild_cache[str(ctx.guild.id)] = 1
            await MessageTemplates.server_archive_message(
                ctx, "Alright, I've changed my active gather mode.", ephemeral=True
            )
        else:
            await ctx.send("guild only.")

    @archive_setup.command(
        name="postcheck",
        description="Check number of stored archived messages that where posted.",
    )
    async def postcheck(self, ctx):
        if ctx.guild:
            mess2 = ArchivedRPMessage.get_archived_rp_messages_with_null_posted_url(
                ctx.guild.id
            )
            mess = ArchivedRPMessage.get_archived_rp_messages_without_null_posted_url(
                ctx.guild.id
            )
            await MessageTemplates.server_archive_message(
                ctx,
                f"About {len(mess)} messages are posted, and {len(mess2)} messages are not posted.",
                ephemeral=True,
            )
        else:
            await ctx.send("guild only.")

    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_channels=True)
    @commands.command(name="lazymode", description="For big, unarchived servers.")
    async def setup_lazy_archive(self, ctx, autochannel: discord.TextChannel, *args):
        if ctx.guild:
            bot = ctx.bot
            guild = ctx.guild
            task_name = "LAZYARCHIVE"
            profile = ServerArchiveProfile.get_or_new(guild.id)
            if profile.history_channel_id == 0:
                await MessageTemplates.get_server_archive_embed(
                    ctx, "Set a history channel first."
                )
                return False
            archive_channel = guild.get_channel(profile.history_channel_id)
            if archive_channel == None:
                await ctx.send("I can't seem to access the history channel, it's gone!")
                return False
            if profile.last_archive_time != None:
                await MessageTemplates.server_archive_message(
                    ctx,
                    "There's no reason for you to use lazy mode, this server already has an active archive.",
                )
                return False
            passok, statusmessage = check_channel(archive_channel)

            if not passok:
                await MessageTemplates.server_archive_message(ctx, statusmessage)
                return
            if not (serverOwner(ctx) or serverAdmin(ctx)):
                await MessageTemplates.server_archive_message(
                    ctx, "You do not have permission to use this command."
                )
                return False
            if LazyContext.get(guild.id) != None:
                await MessageTemplates.server_archive_message(
                    ctx, "There already is a running lazy archive."
                )
                return False
                LazyContext.remove(guild.id)
                if TCGuildTask.get(guild.id, task_name):
                    TCGuildTask.remove_guild_task(guild.id, task_name)

            confirm, mes = await MessageTemplates.confirm(
                ctx,
                "Lazy archive mode WILL take a long time to finish, please make sure you set all your parameters.",
                ephemeral=False,
            )
            if confirm:
                await mes.delete()
                message = await autochannel.send(
                    f"**ATTEMPTING SET UP OF AUTO COMMAND {task_name}**"
                )
                myurl = message.jump_url
                start_date = datetime(2023, 1, 1, 15, 30)
                robj = rrule(freq=MINUTELY, interval=2, dtstart=start_date)

                await setup_lazy_grab(ctx)
                totaltime = ChannelArchiveStatus.get_total_unarchived_time(guild.id)

                lz = LazyContext.create(guild.id)
                if "nocollect" in args:
                    lz.collected = True
                    lz.message_count = ArchivedRPMessage.count_all(guild.id)
                if "nopost" in args:
                    lz.posting = True
                result = f"I've set up the lazy archive system for <#{autochannel.id}>!  The cumulative duration between the earliest and latest messages across all channels is {totaltime.days} days."
                new = TCGuildTask.add_guild_task(guild.id, task_name, message, robj)
                new.to_task(bot)
                bot.database.commit()
                await MessageTemplates.server_archive_message(ctx, result)

        else:
            await mes.delete()
            await ctx.send("guild only.")

    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.command(
        name="reset_archive", description="ADMIN ONLY: WILL RESET THE ARCHIVE GROUPING."
    )
    async def archive_reset(self, ctx):
        if ctx.guild:
            profile = ServerArchiveProfile.get_or_new(ctx.guild.id)
            if profile.history_channel_id == 0:
                await MessageTemplates.get_server_archive_embed(
                    ctx, "Set a history channel first."
                )
                return False
            if not (serverOwner(ctx) or serverAdmin(ctx)):
                await MessageTemplates.server_archive_message(
                    ctx, "You do not have permission to use this command."
                )
                return False
            confirm, mes = await MessageTemplates.confirm(
                ctx, "Are you sure about this?", ephemeral=False
            )

            if confirm:
                await mes.delete()
                ChannelSep.delete_channel_seps_by_server_id(ctx.guild.id)
                ArchivedRPMessage.reset_channelsep_data(ctx.guild.id)
                profile.update(last_group_num=0)
                confirm2, mes2 = await MessageTemplates.confirm(
                    ctx,
                    "I can delete the current history channel if you want to start fresh, is that ok?",
                )
                if confirm2:
                    archive_channel = ctx.guild.get_channel(profile.history_channel_id)
                    cloned = await archive_channel.clone()
                    profile.update(history_channel_id=cloned.id)
                    await archive_channel.delete()
                await mes2.delete()
                profile.last_archive_time = None
                self.bot.database.commit()

                await MessageTemplates.server_archive_message(
                    ctx,
                    "I've reset the grouping data for this server.  When you run another compile_archive, **everything in the archive_channel will be reposted.**",
                )

            else:
                await mes.delete()
        else:
            await ctx.send("guild only.")

    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.command(
        name="delete_archive", description="ADMIN ONLY: WILL DELETE ALL ARCHIVE DATA."
    )
    async def delete_archive(self, ctx):
        if ctx.guild:
            profile = ServerArchiveProfile.get_or_new(ctx.guild.id)
            if profile.history_channel_id == 0:
                await MessageTemplates.get_server_archive_embed(
                    ctx, "Set a history channel first."
                )
                return False
            if not (serverOwner(ctx) or serverAdmin(ctx)):
                await MessageTemplates.server_archive_message(
                    ctx, "You do not have permission to use this command."
                )
                return False

            steps = [
                "# Warning! \n  THIS WILL COMPLETELY ERASE ALL DATA ARCHIVED FROM THIS SERVER!"
                + "\nAre you sure about this?",
                "# This cannont be undone! \n "
                + "Are you sure you want to delete this server's data?",
                "I need one final confirmation before I change the setting.  \n You are sure you want to delete this server's data?",
            ]
            for r in steps:
                confirm, mes = await MessageTemplates.confirm(ctx, r, False)

                if not confirm:
                    await mes.delete()
                    await MessageTemplates.server_archive_message(
                        ctx, "Very well, scope changed aborted.", ephemeral=True
                    )
                    return

            if confirm:
                await mes.delete()
                ChannelSep.delete_channel_seps_by_server_id(ctx.guild.id)
                session = DatabaseSingleton.get_session()
                session.query(ArchivedRPMessage).filter_by(
                    server_id=ctx.guild.id
                ).delete()
                session.commit()
                await ctx.send(ChannelArchiveStatus.count_all(ctx.guild.id))
                ChannelArchiveStatus.delete_status_by_server_id(ctx.guild.id)

                await ctx.send(ChannelArchiveStatus.count_all(ctx.guild.id))
                count = ArchivedRPMessage.count_all(ctx.guild.id)
                await ctx.send(count)
                profile.update(last_group_num=0)
                confirm2, mes = await MessageTemplates.confirm(
                    ctx,
                    "I can delete the current history channel if you want to start fresh, is that ok?",
                    False,
                )

                if confirm2:
                    archive_channel = ctx.guild.get_channel(profile.history_channel_id)
                    cloned = await archive_channel.clone()
                    profile.update(history_channel_id=cloned.id)
                    await archive_channel.delete()
                await mes.delete()
                profile.last_archive_time = None
                self.bot.database.commit()
                mess2 = ArchivedRPMessage.get_archived_rp_messages_with_null_posted_url(
                    ctx.guild.id
                )
                mess = (
                    ArchivedRPMessage.get_archived_rp_messages_without_null_posted_url(
                        ctx.guild.id
                    )
                )
                await MessageTemplates.server_archive_message(
                    ctx,
                    "I've reset the grouping data for this server.  When you run another compile_archive, **everything in the archive_channel will be reposted.**",
                )

            else:
                await mes.delete()
        else:
            await ctx.send("guild only.")

    @commands.command()
    async def firstlasttimestamp(self, ctx):
        """Get the last timestamp of the most recently archived message.
        By default, it only indexes bot/webhook messages.
        """
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id


        profile = ServerArchiveProfile.get_or_new(guildid)

        if profile.history_channel_id == 0:
            await ctx.send("Set a history channel first.")
            return False

        last_time = profile.last_archive_time
        await ctx.send("timestamp:{}".format(last_time.timestamp()))

    @commands.command()
    @commands.is_owner()
    async def setlastfirsttimestamp(self, ctx, time: int):
        """Set the timestamp to begin archiving at."""
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id

        # options.
        update = False
        indexbot = True
        user = False



        profile = ServerArchiveProfile.get_or_new(guildid)

        if profile.history_channel_id == 0:
            await ctx.send("Set a history channel first.")
            return False

        profile.last_archive_time = datetime.fromtimestamp(time)
        self.bot.database.commit()
        await ctx.send("timestamp:{}".format(profile.last_archive_time.timestamp()))

    async def correct(self, ctx, guildid: int, channel: str):
        myseps = ChannelSep.get_channel_seps_by_channel(channel, guildid)
        gui.dprint(len(myseps))

        async def edit_if_needed(target):
            if isinstance(target, ChannelSep):
                message = await urltomessage(target.posted_url, self.bot)

                emb, lc = target.create_embed()
                gui.gprint(lc)
                target.update(neighbor_count=lc)
                await message.edit(embeds=[emb])

        session = DatabaseSingleton.get_session()
        waittime = 0
        for sep in myseps:
            iN, iL = (
                sep.get_neighbor(False, True, False),
                sep.get_neighbor(False, False, False),
            )
            messages = sep.get_messages()
            less = len(messages)
            await ctx.channel.send(less)
            for e, mess in enumerate(messages):
                if mess.posted_url:
                    partial = await urltomessage(mess.posted_url, ctx.bot)
                    try:
                        await partial.add_reaction("❌")
                        ctx.bot.schedule_for_deletion(partial, waittime)
                        waittime += 5
                        # await partial.delete()
                    except Exception as e:
                        gui.gprint(str(e))

                session.delete(mess)
            if sep.posted_url:
                message = await urltomessage(sep.posted_url, ctx.bot)
                await message.delete()
            session.delete(sep)
            session.commit()
            gui.dprint(iN, iL)
            await edit_if_needed(iN)
            gui.dprint(iL)
            await edit_if_needed(iL)
            # cN,cL=self.get_neighbor(True,True),self.get_neighbor(True,False)
        await ctx.channel.send("All target messags deleted.")

    @commands.command()
    @commands.is_owner()
    async def correctit(self, ctx, guildid: int, channel: str):
        await self.correct(ctx, guildid, channel)

    async def edit_embed_and_neighbors(self, target: ChannelSep):
        """
        This code checks if the target ChannelSep object has a
        posted_url attribute, and then edits it's neighbors.

        """

        async def edit_if_needed(target):
            if target:
                message = await urltomessage(target.posted_url, self.bot)

                emb, lc = target.create_embed()
                gui.gprint(lc)
                target.update(neighbor_count=lc)
                await message.edit(embeds=[emb])

        gui.gprint(target, target.posted_url)
        if target.posted_url:
            iL = target.get_neighbor(False, False, False)
            cL = target.get_neighbor(True, False, False)
            gui.gprint(iL, cL, target)

            await edit_if_needed(iL)
            await edit_if_needed(cL)
            gui.gprint("New posted_url value for ChannelSep")

    ##################################### FOR ACTIVE MODE##################################
    # Disabled for now.
    """
    def guild_check(self,guildid):
        #Check if a guild is in the guild cache.
        if self.guild_cache[str(guildid)]==0:
            profile=ServerArchiveProfile.get(guildid)
            if not profile: 
                gui.dprint('unset')
                self.guild_cache[str(guildid)]=1
                return 1
            if profile.archive_dynamic==True:
                gui.dprint("Set")
                self.guild_cache[str(guildid)]=2
            else:
                self.guild_cache[str(guildid)]=1
        return self.guild_cache[str(guildid)]
    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        if not message.guild: return
        guildid=message.guild.id

        if self.guild_check(guildid)==2:
            profile= self.guild_db_cache[str(guildid)]
            if not profile: 
                profile=profile=ServerArchiveProfile.get(guildid)
                self.guild_db_cache[str(guildid)]=profile
            
            actx=ArchiveContext(self.bot,profile=profile)
            if not actx.evaluate_add(message):
                gui.gprint("scope failure.")
                return
            if not actx.evaluate_channel(message):
                gui.gprint("channel failure.")
                return
            gui.gprint("Message added.")
            await HistoryMakers.get_history_message(message,active=True)

        pass
    @commands.Cog.listener()
    async def on_message_edit(self,before,message):
        if not message.guild: return
        guildid=message.guild.id

        if self.guild_check(guildid)==2:
            profile= self.guild_db_cache[str(guildid)]
            if not profile: 
                profile=profile=ServerArchiveProfile.get(guildid)
                self.guild_db_cache[str(guildid)]=profile
            if not profile: return
            if profile.archive_dynamic==True:
                m,e=ArchivedRPMessage.get(server_id=guildid,message_id=message.id)
                if m!=0:
                    e.update(content=message.clean_conent)
                    self.bot.database.commit()
        
    @commands.Cog.listener()
    async def on_message_delete(self,message):
        if not message.guild: return
        guildid=message.guild.id
        if self.guild_check(guildid)==2:
            profile= self.guild_db_cache[str(guildid)]
            if not profile: 
                profile=profile=ServerArchiveProfile.get(guildid)
                self.guild_db_cache[str(guildid)]=profile
            if not profile: return
            if profile.archive_dynamic==True:
                m,entry=ArchivedRPMessage.get(server_id=guildid,message_id=message.id)
                if m==2: #It was found, and is currently set to 'active'
                    session=self.bot.database.get_session()
                    session.delete(entry)
                    session.commit()
    """

    @commands.command(
        name="archive_compile_lazy",
        brief="start archiving the server.  ",
        extras={"guildtask": ["rp_history"]},
    )
    async def compileArchiveChannelLazy(self, ctx):
        await ctx.send("Coming soon.")

    @commands.hybrid_command(
        name="compile_archive",
        brief="start archiving the server.  Will only archive messages based on defined archive scope.",
        extras={"guildtask": ["rp_history"]},
    )
    async def compileArchiveChannel(self, ctx, send_all_clear_message: bool = True):
        """Compile all messages into archive channel.  This can be invoked with options.
        +`full` - get the full history of this server
        +`update` -only update the current archive channel.  DEFAULT.

        +`ws` - compile only webhooks/BOTS.  DEFAULT.
        +`user` - complile only users
        +`both` -compile both

        """

        # SETUP
        bot = ctx.bot
        channel = ctx.message.channel
        guild: discord.Guild = channel.guild
        if guild == None:
            await ctx.send("This command will only work inside a guild.")
            return
        from cogs.ArchiveSub.archive_compiler import ArchiveCompiler

        if LazyContext.get(guild.id) != None:
            await ctx.send("There is an active lazy archive in progress, please wait.")
            return
        actx = ArchiveCompiler(ctx, send_all_clear_message=send_all_clear_message)
        outcome = await actx.start()
        if outcome:
            self.guild_db_cache[str(guild.id)] = outcome
            bot.database.commit()

    @commands.command(extras={"guildtask": ["rp_history"]})
    async def makeCalendar(self, ctx):
        """Create a calendar of all archived messages with dates in this channel."""
        bot = ctx.bot
        channel = ctx.message.channel
        guild = channel.guild
        guildid = guild.id
        gui.dprint("calendar maek")
        profile = ServerArchiveProfile.get_or_new(guildid)

        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(
                ctx, "Set a history channel first."
            )
            return False
        if channel.id == profile.history_channel_id:
            return False
        archive_channel = guild.get_channel(profile.history_channel_id)
        if archive_channel == None:
            await MessageTemplates.get_server_archive_embed(
                ctx, "I can't seem to access the history channel, it's gone!"
            )
            return False

        thread = discord.utils.get(archive_channel.threads, name="Message Calendar")
        if thread:
            await thread.delete()
        new_thread = await archive_channel.create_thread(
            name="Message Calendar",
            auto_archive_duration=10080,
            type=discord.ChannelType.public_thread,
        )

        async def calendarMake(
            guildid,
            lastday=None,
            this_dates=["█", "█", "█", "█", "█", "█", "█"],
            current_calendar_embed_object=None,
            weeknumber=0,
        ):
            this_dates = ["█", "█", "█", "█", "█", "█", "█"]
            au = ctx.bot.user.avatar.url

            def get_seps_between_dates(start, end):
                """this generator returns lists of all separators that are on the specified dates."""
                cd = start
                while cd <= end:
                    dc = 0
                    gui.dprint(cd)
                    se = ChannelSep.get_all_separators_on_date(guildid, cd)
                    if se:
                        for tm in se:
                            dc += tm.message_count
                        yield {
                            "date": cd.date(),
                            "url": se[0].posted_url,
                            "mc": dc,
                            "sc": len(se),
                        }
                    cd += timedelta(days=1)

            async def post(cceo):
                await web.postWebhookMessageProxy(
                    new_thread,
                    message_content="",
                    display_username="Archive Calendar",
                    avatar_url=au,
                    embed=[cceo],
                )

            def same_week(d1, d2):
                return d1.isocalendar()[1] == d2.isocalendar()[1] and d1.year == d2.year

            def same_month(d1, d2):
                return d1.month == d2.month and d1.year == d2.year

            async def lti(cceo, wn, this_dates, lastday, date):
                if not same_week(lastday, date):
                    cceo.add_field(
                        name=f"Week {wn}", value="\n".join(this_dates), inline=True
                    )
                    this_dates, wn = ["█", "█", "█", "█", "█", "█", "█"], wn + 1
                if not same_month(lastday, date):
                    cceo.add_field(
                        name=f"Week {wn}", value="\n".join(this_dates), inline=True
                    )
                    this_dates, wn = ["█", "█", "█", "█", "█", "█", "█"], 0
                    await post(cceo)
                    cceo, wn = discord.Embed(title=date.strftime("%B %Y")), 0
                return wn, cceo, this_dates

            start, end = ChannelSep.get_first_and_last_dates(guildid)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=1
            )
            gui.dprint(";ok")
            for day in get_seps_between_dates(start, end):
                date, url, mc = day["date"], day["url"], day["mc"]
                if current_calendar_embed_object == None:
                    current_calendar_embed_object = discord.Embed(
                        title=date.strftime("%B %Y")
                    )
                if lastday != None:
                    weeknumber, current_calendar_embed_object, this_dates = await lti(
                        current_calendar_embed_object,
                        weeknumber,
                        this_dates,
                        lastday,
                        date,
                    )
                else:
                    current_calendar_embed_object = discord.Embed(
                        title=date.strftime("%B %Y")
                    )
                strday = date.strftime("%m-%d-%Y")
                this_dates[date.weekday()] = "[{}]({})-{}".format(strday, url, mc)
                lastday = date
            current_calendar_embed_object.add_field(
                name="Week {}".format(weeknumber),
                value="\n".join(this_dates),
                inline=True,
            )
            await post(current_calendar_embed_object)

        await calendarMake(guildid)


async def setup(bot):
    gui.dprint(__name__)
    # from .ArchiveSub import setup
    # await bot.load_extension(setup.__module__)
    await bot.add_cog(ServerRPArchive(bot))


async def teardown(bot):
    # from .ArchiveSub import setup
    # await bot.unload_extension(setup.__module__)
    await bot.remove_cog("ServerRPArchive")
