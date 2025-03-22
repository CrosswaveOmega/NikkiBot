import base64
import datetime
from collections import defaultdict
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from langchain.docstore.document import Document

import cogs.ResearchAgent as ra

import gui
from assetloader import AssetLookup
from bot import TC_Cog_Mixin, super_context_menu
from database.database_note import NotebookAux

from utility.debug import Timer
from utility.embed_paginator import pages_of_embed_attachments, pages_of_embeds
from utility.mytemplatemessages import MessageTemplates
from utility.views import BaseView

from .AICalling import AIMessageTemplates

# import datetime


async def owneronly(interaction: discord.Interaction):
    return await interaction.client.is_owner(interaction.user)


topictype = app_commands.Range[str, 2, 128]
keytype = app_commands.Range[str, 2, 128]
contenttype = app_commands.Range[str, 5, 4096]


async def file_to_data_uri(file: discord.File) -> str:
    # Read the bytes from the file
    with BytesIO(file.fp.read()) as f:
        # Read the bytes from the file-like object
        file_bytes = f.read()
    # Base64 encode the bytes
    base64_encoded = base64.b64encode(file_bytes).decode("ascii")
    # Construct the data URI
    data_uri = f"data:{'image'};base64,{base64_encoded}"
    return data_uri


async def data_uri_to_file(data_uri: str, filename: str) -> discord.File:
    # Split the data URI into its components
    metadata, base64_data = data_uri.split(",")
    # Get the content type from the metadata
    content_type = metadata.split(";")[0].split(":")[1]
    # Decode the base64 data
    file_bytes = base64.b64decode(base64_data)
    # Create a discord.File object
    file = discord.File(BytesIO(file_bytes), filename=filename, spoiler=False)
    return file


class NoteContentModal(discord.ui.Modal, title="Enter Note Contents"):
    """Modal for editing note data"""

    def __init__(self, *args, content=None, key=None, topic=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.followup_input = discord.ui.TextInput(
            label="Enter Content here.",
            max_length=4000,
            default=content,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.followup_input)
        self.keyinput = discord.ui.TextInput(
            label="Enter key", max_length=128, default=key, required=True
        )
        self.topicvalue = discord.ui.TextInput(
            label="Enter topic", max_length=128, default=topic, required=True
        )
        self.add_item(self.keyinput)
        self.add_item(self.topicvalue)

    async def on_submit(self, interaction):
        followup = self.followup_input.value
        key = self.keyinput.value
        topic = self.topicvalue.value
        self.done = (followup, key, topic)
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        self.stop()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        return await super().on_error(interaction, error)


class NoteEditView(BaseView):
    """
    View that allows one to edit the work in progress notes.
    """

    def __init__(
        self,
        *,
        user,
        timeout=30 * 15,
        content=None,
        key=None,
        topic=None,
        has_image=False,
    ):
        super().__init__(user=user, timeout=timeout)
        self.value = False
        self.done = None
        self.content = content
        self.key = key
        self.has_image = has_image
        self.topic = topic

    def make_embed(self):
        embed = discord.Embed(
            description=f"{self.content}"[:4000],
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="topic", value=self.topic)

        embed.add_field(name="key", value=self.key)
        if not self.is_finished():
            embed.add_field(
                name="timeout",
                value=f"timeout in: {discord.utils.format_dt(self.get_timeout_dt(), 'R')}",
                inline=False,
            )
        if self.has_image:
            embed.add_field(
                name="Image Display",
                value="Your real note will have your uploaded image added, but for efficiency sake a placeholder is used for this preview.",
                inline=False,
            )
            embed.set_image(url="https://picsum.photos/400/200.jpg")
        return embed

    async def on_timeout(self) -> None:
        self.value = "timeout"
        self.stop()

    @discord.ui.button(label="Edit note", style=discord.ButtonStyle.primary, row=1)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NoteContentModal(
            content=self.content, key=self.key, topic=self.topic, timeout=self.timeout
        )
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done:
            c, k, t = modal.done
            self.content = c if c is not None else self.content
            self.key = k if k is not None else self.key
            self.topic = t if t is not None else self.topic
            self.update_timeout()
            await interaction.edit_original_response(embed=self.make_embed())
            # await self.note_add_callback(interaction,c,k,t)
        else:
            await interaction.edit_original_response(content="Cancelled")

    @discord.ui.button(label="Complete", style=discord.ButtonStyle.green, row=4)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not (self.content and self.key and self.topic):
            await interaction.response.edit_message(
                content="You are missing the content, key, or topic!",
                embed=self.make_embed(),
            )
        else:
            await interaction.response.edit_message(
                content="Complete", embed=self.make_embed()
            )
            self.value = True
            self.done = (self.content, self.key, self.topic)
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Canceled", embed=self.make_embed()
        )
        self.value = False
        self.stop()






class Global(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot: commands.Bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        self.globalonly = True
        self.memehook = AssetLookup.get_asset("memehook", "urls")
        self.usertopics = {}
        self.copies: Dict[int, discord.Message] = {}
        self.init_context_menus()

    @super_context_menu(name="Extracool", flags="user")
    async def coooler(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        cont = message.content
        guild = message.guild
        embed = discord.Embed(description=f"It says *{message.content}")
        if hasattr(message, "author"):
            embed.add_field(
                name="Author", value=f"* {str(message.author)}{type(message.author)}, "
            )

        if hasattr(message, "jump_url"):
            embed.add_field(name="url", value=f"* {str(message.jump_url)}, ")
        if hasattr(message, "channel"):
            embed.add_field(name="channel", value=f"* {str(message.channel)}, ")
            if hasattr(message.channel, "parent"):
                embed.add_field(
                    name="parent", value=f"* {str(message.channel.parent)}, "
                )
        if interaction.guild_id:
            embed.add_field(name="guildid", value=interaction.guild_id)

        await interaction.response.send_message(
            content="Message details below.",
            ephemeral=True,
            embed=embed,
        )

    @super_context_menu(name="CopyMessage", flags="user")
    async def memethief(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        username = interaction.user.display_name
        avatar = str(interaction.user.avatar)
        content = message.content
        embeds = message.embeds

        userid = interaction.user.id
        self.copies[userid] = message

        cont = message.content
        guild = message.guild
        embed = discord.Embed(description=f"It says *{message.content}")
        if hasattr(message, "author"):
            embed.add_field(
                name="Author", value=f"* {str(message.author)}{type(message.author)}, "
            )

        if hasattr(message, "jump_url"):
            embed.add_field(name="url", value=f"* {str(message.jump_url)}, ")
        if hasattr(message, "channel"):
            embed.add_field(name="channel", value=f"* {str(message.channel)}, ")
            if hasattr(message.channel, "parent"):
                embed.add_field(
                    name="parent", value=f"* {str(message.channel.parent)}, "
                )
        if interaction.guild_id:
            embed.add_field(name="guildid", value=interaction.guild_id)

        await interaction.response.send_message(
            content="Message copied.",
            ephemeral=True,
            embed=embed,
        )

    @super_context_menu(name="usercool", flags="user")
    async def coooler2(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        embed = discord.Embed(
            description=f"This user is {user}.\n avatar {user.avatar.url}"
        )

        await interaction.response.send_message(
            content="User details below.",
            ephemeral=True,
            embed=embed,
        )

    @app_commands.command(name="paste", description="paste_message")
    @app_commands.allowed_installs(users=True)
    async def paste_message(self, interaction: discord.Interaction) -> None:
        """Do a web search"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        if ctx.author.id not in self.copies:
            await ctx.send("You did not copy any messages", ephemeral=True)
            return
        message = self.copies[ctx.author.id]
        message.author.name
        files = []
        for a in message.attachments:
            this_file = await a.to_file()
            files.append(this_file)

        embed = discord.Embed(description=message.content[:4000])
        embed.set_author(
            name=str(message.author.name), icon_url=message.author.avatar.url
        )
        embs = []
        for e in message.embeds:
            if e.type == "rich":
                embs.append(e)
        if embs:
            embed.add_field(name="embeds", value=f" {len(embs)} embeds")
        embed.add_field(name="URL", value=f"[original]({message.jump_url})")
        embed.timestamp = message.created_at
        await ctx.send(embed=embed, files=files, ephemeral=True)
        cont, mess = await MessageTemplates.confirm(
            ctx,
            "Repost?",
            True,
        )
        await mess.delete()
        if not cont:
            return
        try:
            embed = discord.Embed(description=message.content[:4000])
            embed.set_author(
                name=str(message.author.name),
                icon_url=message.author.avatar.url,
                url=message.jump_url,
            )
            embs = []
            files = []
            for a in message.attachments:
                this_file = await a.to_file()
                if a.content_type.startswith("image/"):
                    embed.set_image(url=f"attachment://{this_file.filename}")
                files.append(this_file)

            guild, icon = None, None
            if message.guild:
                guild = message.guild.name
                if message.guild.icon:
                    icon = message.guild.icon.url
            for e in message.embeds:
                if e.type == "rich":
                    embs.append(e)
            if embs:
                embed.add_field(name="embeds", value=f" {len(embs)} embeds")
            ref = message.reference
            if ref and isinstance(ref.resolved, discord.Message):
                try:
                    embed.add_field(
                        name="Replying to...",
                        value=f"[{ref.resolved.author}]({ref.resolved.jump_url})",
                        inline=False,
                    )
                except Exception as e:
                    await ctx.bot.send_error(e, "Paste error", True)
            embed.add_field(name="URL", value=f"[original]({message.jump_url})")
            if guild:
                embed.set_footer(text=f"From {guild}", icon_url=icon)
            embed.timestamp = message.created_at

            embs.insert(0, embed)
            await ctx.send(embeds=embs, files=files, ephemeral=False)
            return

        except Exception as e:
            await ctx.send(f"{e}", ephemeral=True)

    @app_commands.command(name="search", description="search the interwebs.")
    @app_commands.describe(query="Query to search google with.")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def websearch(self, interaction: discord.Interaction, query: str) -> None:
        """Do a web search"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> Searching", ephemeral=True
        )
        results = ra.tools.google_search(ctx.bot, query, 7)
        allstr = ""
        emb = discord.Embed(title=f"Search results {query}")
        readable_links = []

        def indent_string(inputString, spaces=2):
            indentation = " " * spaces
            indentedString = "\n".join(
                [indentation + line for line in inputString.split("\n")]
            )
            return indentedString

        outputthis = f"### Search results for {query} \n\n"
        for r in results["items"]:
            desc = r.get("snippet", "NA")
            allstr += r["link"] + "\n"
            emb.add_field(
                name=f"{r['title'][:200]}",
                value=f"{r['link']}\n{desc}"[:1000],
                inline=False,
            )
            outputthis += f"+ **Title: {r['title']}**\n **Link:**{r['link']}\n **Snippit:**\n{indent_string(desc, 1)}"
        await mess.edit(content=None, embed=emb)

    @app_commands.command(name="supersearch", description="use db search.")
    @app_commands.describe(query="Query to search DB for")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def doc_talk(self, interaction: discord.Interaction, query: str) -> None:
        """get bot info for this server"""
        owner = await interaction.client.is_owner(interaction.user)
        if not owner:
            await interaction.response.send_message("This command is owner only.")
            return

        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> Searching", ephemeral=True
        )
        try:
            ans, source, _ = await ra.actions.research_op(query, 9)
            emb = discord.Embed(description=ans)
            emb.add_field(name="source", value=str(source)[:1000], inline=False)
            audit = await AIMessageTemplates.add_emb_audit(ctx, embed=emb)

            await mess.edit(content=None, embed=emb)
        except Exception as e:
            await self.bot.send_error(e, "AIerr", True)
            await ctx.send("something went wrong...")

    @app_commands.command(name="pingtest", description="ping")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def ping(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")

    @app_commands.command(name="context_test", description="ping")
    @app_commands.allowed_installs(users=True)
    async def ping2(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")


async def setup(bot):
    #await bot.add_cog(NotesCog(bot))
    await bot.add_cog(Global(bot))


async def teardown(bot):
    #await bot.remove_cog("NotesCog")
    await bot.remove_cog("Global")
