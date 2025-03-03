import json
from typing import Literal
import discord
import asyncio

# import datetime


from discord.ext import commands

from discord import app_commands
from utility import MessageTemplates, RRuleView, formatutil
from utility.embed_paginator import pages_of_embeds
from bot import TC_Cog_Mixin


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
            if mychannel:
                chan = self.bot.get_channel(int(mychannel))
                await chan.send(embed=embed)
        await interaction.response.send_message(
            "Thanks for your feedback!  I will save it to my feedback file.",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )


class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.my_count = {}

    async def callback(self, interaction, button):
        user = interaction.user
        label = button.label
        if str(user.id) not in self.my_count:
            self.my_count[str(user.id)] = 0
        self.my_count[str(user.id)] += 1
        await interaction.response.send_message(
            f"You are {user.name}, this is {label}, and you have pressed the buttons {self.my_count[str(user.id)]} times.",
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


class General(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        bot.add_view(PersistentView())

    @commands.command()
    async def hashtest(self, ctx, string: str, length: int = 5):
        hlist = hash.get_hash_sets()
        for i in hlist:
            has, hint = hash.hash_string(
                string_to_hash=string, hashlen=length, hashset=i
            )
            await ctx.send(f"{has}\n{hint}")

    @commands.command()
    async def create_rruleview(self, ctx):
        """THIS FUNCTION IS FOR TESTING THE RRULE GENERATING VIEW."""
        await ctx.send(
            "Welcome to the RRule Generator!\nPlease provide the following information:"
        )

        view = RRuleView(ctx.author)
        message = await ctx.send("Select the frequency:", view=view)
        await asyncio.sleep(2)
        await view.wait()
        if view.value:
            await ctx.send(f"`{str(view.value)}`")
        else:
            await ctx.send("cancelled")
        await message.delete()

    @app_commands.command(name="server_info", description="view the server data")
    async def info(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        member_count = guild.member_count
        channel_count = len(guild.channels)
        cats = len(
            [i for i in guild.channels if i.type == discord.ChannelType.category]
        )
        blocked, can_see = 0, 0
        messagable, history_view = 0, 0
        c_mess, c_manage = 0, 0
        messagableperms = [
            "send_messages",
            "embed_links",
            "attach_files",
            "add_reactions",
            "use_external_emojis",
            "use_external_stickers",
            "read_message_history",
            "manage_webhooks",
        ]
        manageableperms = ["manage_channels", "manage_permissions"]
        for channel in guild.text_channels:
            perms = channel.permissions_for(guild.me)
            if perms.view_channel:
                can_see += 1
                messageable_check = []
                manageable_check = []
                if perms.read_message_history:
                    history_view += 1
                if perms.send_messages:
                    for p, v in perms:
                        if v:
                            if p in messagableperms:
                                messageable_check.append(p)
                            if p in manageableperms:
                                manageable_check.append(p)
                    messagable += 1
                    if all(elem in messagableperms for elem in messageable_check):
                        c_mess += 1
                    if all(elem in manageableperms for elem in manageable_check):
                        c_manage += 1

            else:
                blocked += 1

        view = f"Categories:{cats}\n Viewable:{can_see} channels.  \nArchivable: {history_view} channels."
        view2 = f"Messagable: {messagable} channels.  \n Of which, {messagable - c_mess} channels have a restriction."
        desc = f"Members: {member_count}\n Channels: {channel_count}\n{view}\n{view2}"

        emb = await MessageTemplates.server_profile_message(
            ctx, description=desc, ephemeral=True
        )

    @app_commands.command(
        name="emojis",
        description="Print out all emojis I have access to from this server.",
    )
    @app_commands.guild_only()
    async def emojiinfo(
        self, interaction: discord.Interaction, scope: Literal["server", "all"] = "all"
    ) -> None:
        """print out a list of all emojis within the invoked server."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        member_count = guild.member_count

        if guild:
            emojis = []
            to_use = ctx.bot.emojis
            if scope == "server":
                to_use = ctx.guild.emojis

            for emoji in to_use:
                emoji_format = f"<:{emoji.name}:{emoji.id}>`<:{emoji.name}:{emoji.id}>`"
                if emoji.animated:
                    emoji_format = (
                        f"<a:{emoji.name}:{emoji.id}>`<a:{emoji.name}:{emoji.id}>`"
                    )
                emojis.append(emoji_format)
            num_emojis = len(emojis)
            emoji_strings = [
                " \n".join([emoji for emoji in emojis[i : i + 25]])
                for i in range(0, num_emojis, 25)
            ]
            elist = await MessageTemplates.server_profile_embed_list(ctx, emoji_strings)
            await pages_of_embeds(ctx, elist, ephemeral=True)
        else:
            await ctx.send("Guild not found.", ephemeral=True)

    @app_commands.command(
        name="progress_test", description="Test out the progress bar."
    )
    @app_commands.guild_only()
    async def progresstest(
        self, interaction: discord.Interaction, total: int = 10, width: int = 5
    ) -> None:
        """Just test out the progress bar"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        member_count = guild.member_count

        if guild:
            pager = commands.Paginator(prefix="", suffix="")
            for i in range(total + 1):
                percent = round((i / total) * 100.0, 2)
                bar = formatutil.progress_bar(i, total, width=width)
                pager.add_line(f"{percent}%:{bar}")
            for p in pager.pages:
                await ctx.send(p)
        else:
            await ctx.send("Guild not found.", ephemeral=True)

    @app_commands.command(name="ping")
    async def pings(self, interaction: discord.Interaction):
        """just check if my app commands work."""
        await interaction.response.send_message("pong")

    @commands.hybrid_command(name="persistent_view")
    async def constant_view(self, ctx):
        """This command returns a persistent view, as a test."""
        await ctx.send("Here's some buttons.", view=PersistentView())

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
            await ctx.send("Timeout...", epheremal=True)


async def setup(bot):
    await bot.add_cog(General(bot))
