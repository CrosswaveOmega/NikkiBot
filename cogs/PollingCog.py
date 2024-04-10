from typing import NewType
import gui
import asyncio
import discord
from discord.ext import commands
import json
import os
from typing import List, Literal
import discord


# import datetime
from datetime import datetime, timedelta
import io
from queue import Queue
from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook

import random
import operator
from random import randint, seed
from bot import TCGuildTask, Guild_Task_Functions, TCBot, TC_Cog_Mixin
import traceback

from discord import app_commands
from discord.app_commands import Choice
from .Polling import *
from utility import pages_of_embeds, urltomessage
from utility import serverOwner, serverAdmin
from database import ServerArchiveProfile


class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.my_count = {}

    async def callback(self, interaction, button):
        user = interaction.user
        label = button.label
        if not str(user.id) in self.my_count:
            self.my_count[str(user.id)] = 0
        self.my_count[str(user.id)] += 1
        await interaction.response.send_message(
            f"You are {user.name}, this is {label}, and you have pressed this button {self.my_count[str(user.id)]} times.",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            f"Oops! Something went wrong, {str(error)}", ephemeral=True
        )

    @discord.ui.button(
        label="Green",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:green",
    )
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, button)

    @discord.ui.button(
        label="Red", style=discord.ButtonStyle.red, custom_id="persistent_view:red"
    )
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, button)

    @discord.ui.button(
        label="Blue",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_view:blue",
    )
    async def blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, button)

    @discord.ui.button(
        label="Grey", style=discord.ButtonStyle.grey, custom_id="persistent_view:grey"
    )
    async def grey(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, button)


class Feedback(discord.ui.Modal, title="Feedback"):
    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    name = discord.ui.TextInput(
        label="title",
        placeholder="Please title your suggestion.",
        required=True,
        max_length=256,
    )

    feedback = discord.ui.TextInput(
        label="description",
        style=discord.TextStyle.paragraph,
        placeholder="Type your feedback here...",
        required=True,
        max_length=1024,
    )

    async def on_submit(self, interaction: discord.Interaction):
        with open("feedback.txt", "a") as f:
            feedback_dict = {"name": self.name.value, "feedback": self.feedback.value}

            f.write(json.dumps(feedback_dict) + "\n")
            embed = discord.Embed(
                title=self.name.value,
                description=self.feedback.value,
                color=discord.Color.random(),
            )
            embed.set_author(
                name=f"Sent by: {interaction.user.name}",
                icon_url=interaction.user.avatar.url,
            )
            mychannel = self.bot.config.get("optional", "feedback_channel_id")
            gui.dprint("ok")
            if mychannel:
                chan = self.bot.get_channel(int(mychannel))
                await chan.send(embed=embed)
        await interaction.response.send_message(
            f"Thanks for your feedback!  I will save it to my feedback file.",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )


PollChoices = NewType("PollChoices", int)


def validate_poll_choices(n: int) -> PollChoices:
    if n < 2:
        raise ValueError("Poll must have at least 2 choices")
    elif n > 5:
        raise ValueError("Poll cannot have more than 5 choices")
    return PollChoices(n)


"""
**Creating a Poll**

To create a new poll, use the /make_poll command. 
This will bring up an interactive UI 
where you can specify the name, poll text, 
number of options, the text for each option, and the duration of the poll. 
Polls can last up to seven days and 23 hours
 Note that right now, newly created polls are restricted to the server in which they are created.

**Participating in a Poll**

After a poll has been created, the poll can be accessed through any linked message.
 These buttons are persistent views and will automatically update whenever a user votes in the poll. 
 You can vote on a poll by clicking one of the buttons associated with the poll.

**Posting Polls**

Server moderators can set up a specific poll channel using the /setup_poll_channel command.
 This channel will be used to display newly created polls. 
 This can help to keep polls organized and easy to find.

### Poll Results

Once a poll has ended, the buttons are removed from each message and the final results are displayed. 
"""


class PollingCog(commands.Cog, TC_Cog_Mixin):
    """For Server Polls"""

    def __init__(self, bot: TCBot):
        self.helptext = """
        
            The PollingCog allows users to create and participate in polls in their server or globally. 

        """
        PollTable.update_poll_status()
        self.bot = bot
        try:
            for i in PollMessages.get_active_poll_messages():
                p, mes = i
                for w in mes:
                    m, u = w
                    bot.add_view(Persistent_Poll_View(p), message_id=m)
            bot.add_view(PersistentView())
        except Exception as e:
            gui.gprint(e)
        self.message_update_cleanup.start()

    def cog_unload(self):
        self.message_update_cleanup.cancel()

    def server_profile_field_ext(self, guild: discord.Guild):
        """return a dictionary for the serverprofile template message"""
        profile = PollChannelSubscribe.get(guild.id)
        if not profile:
            return None
        auto_log_chan = f"<#{profile.channel_id}>"
        output = f"Polling Channel:{auto_log_chan}"
        field = {"name": "Server Poll System", "value": output}
        return field

    async def add_poll_message(
        self, channel: discord.abc.Messageable, poll: PollTable, ephemeral=False
    ):
        if poll:
            emb = poll.poll_embed_view()
            if poll.is_active():
                if not ephemeral:
                    view = Persistent_Poll_View(poll)
                    message = await channel.send(embed=emb, view=view)
                    PollMessages.add_poll_message(poll.poll_id, message)
                else:
                    view = Persistent_Poll_View(poll)
                    message = await channel.send(embed=emb, view=view, ephemeral=True)
                return ""
            else:
                await channel.send(embed=emb)
                return ""
        else:
            return "Invalid poll id"

    async def poll_subscription(self):
        """update polls in all subscribed channels."""
        try:
            polllist = PollChannelSubscribe.get_new_polls()
            gui.gprint(polllist)
            for i in polllist:
                channel_id, polls = i
                channel = self.bot.get_channel(channel_id)
                if channel:
                    for p in polls:
                        res = await self.add_poll_message(channel, p)

        except Exception as e:
            await self.bot.send_error(e, "subscription")

    @tasks.loop(minutes=5)
    async def message_update_cleanup(self):
        try:
            PollTable.update_poll_status()
            for i in PollMessages.get_active_poll_messages():
                poll, mes = i
                gui.gprint(mes)
                for w in mes:
                    m, u = w
                    gui.gprint(u)
                    if poll.change_vote:
                        embed = poll.poll_embed_view()
                        message = await urltomessage(u, self.bot, partial=True)
                        try:
                            await message.edit(embed=embed)
                        except Exception as e:
                            gui.gprint(e)
                            PollMessages.remove_poll_message(m)
                if poll.change_vote:
                    poll.change_vote = False
                    self.bot.database.commit()
                # await asyncio.sleep(4)
            for i in PollMessages.get_inactive_poll_messages():
                poll, mes = i
                for w in mes:
                    m, u = w
                    message = await urltomessage(u, self.bot)
                    if message:
                        await message.edit(embed=poll.poll_embed_view(), view=None)
            PollMessages.remove_invalid_poll_messages()
        except Exception as e:
            await self.bot.send_error(e, f"Message update cleanup error.")
            gui.gprint(str(e))

    @app_commands.command(
        name="setup_poll_channel",
        description="admin only-Set a channel to post newly created polls in.",
    )
    @app_commands.describe(autochannel="The channel you want polls to be posted in.")
    async def pollchannelmake(self, interaction, autochannel: discord.TextChannel):
        """Add a poll channel to a server."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        if not (serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.poll_message(
                ctx, "You do not have the right permissions to set this."
            )
            return False
        # check if the passed in autochannel meets the standards.
        passok, statusmessage = Guild_Task_Functions.check_auto_channel(autochannel)

        if not passok:
            await MessageTemplates.poll_message(ctx, statusmessage)
            return

        prof = ServerArchiveProfile.get(server_id=guild.id)
        if prof:
            if autochannel.id == prof.history_channel_id:
                result = f"this should not be the same channel as the archive channel.  Specify a different channel such as a bot spam channel."
                await MessageTemplates.poll_message(ctx, result)
                return
        PollChannelSubscribe.set_or_update(
            server_id=guild.id, channel_id=autochannel.id
        )
        await MessageTemplates.poll_message(
            ctx,
            title="Poll Setup Outcome",
            description="I've set your polling channel up!",
        )

    @app_commands.command(
        name="poll_channel_update", description="Force update for polling."
    )
    async def pollsub(self, interaction: discord.Interaction):
        """Force poll_subscription to run."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        await self.poll_subscription()
        await ctx.send("sub done.")

    pc = app_commands.Group(name="polls", description="Commands for the poll system.")

    @pc.command(name="make_poll", description="Make a Discord Poll for this server..")
    @app_commands.describe(
        scope="The scope of your poll, can be either 'server' or global"
    )
    async def make_poll(
        self,
        interaction: discord.Interaction,
        scope: Literal["server", "global"] = "server",
    ):
        """make a poll!"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        if scope == "global" and ctx.author.id != self.bot.application.owner.id:
            await MessageTemplates.poll_message(
                ctx,
                title="No permissions",
                description="I'm sorry.  Currently, only my owner can make global polls.  This is to prevent spam.",
                ephemeral=True,
            )
            return

        poll_edit_view = PollEdit(user=ctx.author, scope=scope, server_id=ctx.guild.id)
        message = await ctx.send(
            "Please note, there's a timeout of 15 minutes.",
            embed=discord.Embed(title="getting started?"),
            view=poll_edit_view,
        )
        await asyncio.sleep(2)
        await poll_edit_view.wait()
        if poll_edit_view.value == True:
            newpoll = poll_edit_view.my_poll
            time_delta = timedelta(
                days=newpoll["days"], hours=newpoll["hours"], minutes=newpoll["minutes"]
            )
            new_datetime = datetime.now() + time_delta
            newpoll.pop("days")
            newpoll.pop("hours")
            newpoll.pop("minutes")
            poll = PollTable.new_poll(
                made_by=ctx.author.id, end_date=new_datetime, **newpoll
            )
            await message.delete()
            await MessageTemplates.poll_message(
                ctx,
                f"I've made your poll!  You can find it at poll id: {poll.poll_id}",
                ephemeral=True,
            )
            await self.poll_subscription()
        else:
            await ctx.send("Op Cancelled.", ephemeral=True)
            await message.delete()

    @pc.command(name="list_polls", description="get all currently active polls.")
    async def view_polls(self, interaction: discord.Interaction):
        """view a list of active polls!"""
        ctx = await self.bot.get_context(interaction)
        if not ctx.guild:
            await MessageTemplates.poll_message(
                ctx, "This poll id is invalid.", ephemeral=True
            )
            return
        act = PollTable.get_active_polls(ctx.guild.id)
        gui.gprint(act)
        embeds = PollTable.poll_list(act)
        await pages_of_embeds(ctx, embeds, ephemeral=True)

    @pc.command(
        name="get_poll",
        description="open a a temporary voting message that will let you vote in a poll!",
    )
    @app_commands.describe(poll_id="The ID of the poll you want to vote in.")
    async def view_poll(self, interaction: discord.Interaction, poll_id: int):
        """view a poll!"""
        ctx = await self.bot.get_context(interaction)
        if not ctx.guild:
            await ctx.send("This command does not work in dms.")
            return
        poll = PollTable.get(poll_id)
        result = await self.add_poll_message(ctx, poll, ephemeral=True)
        if result:
            await MessageTemplates.poll_message(
                ctx, "This poll id is invalid.", ephemeral=True
            )

    @app_commands.command(name="ping")
    async def pings(self, interaction: discord.Interaction):
        """just check if my app commands work..."""
        await interaction.response.send_message("pong")

    @commands.hybrid_command(name="persistent_view")
    async def constant_view(self, ctx):
        """This command returns a persistent view, as a test."""
        await ctx.send("What's your favourite colour?", view=PersistentView())

    @app_commands.command(
        name="nikkifeedback",
        description="Have a suggestion or complaint?  Use this and let me know!",
    )
    async def feedback_send(self, interaction: discord.Interaction):
        """test for a feedback system"""
        modal = Feedback(self.bot, timeout=60)
        await interaction.response.send_modal(modal)
        res = await modal.wait()
        ctx = self.bot.get_context(interaction)
        if res:
            await ctx.send(f"{modal.name.value}", epheremal=True)
            await ctx.send(f"{modal.feedback.value}", epheremal=True)
        else:
            await ctx.send(f"Timeout...", epheremal=True)


async def setup(bot):
    gui.dprint(__name__)
    # from .Polling import setup
    # await bot.load_extension(setup.__module__)
    await bot.add_cog(PollingCog(bot))


async def teardown(bot):
    # from .Polling import setup
    # await bot.unload_extension(setup.__module__)
    await bot.remove_cog("PollingCog")
