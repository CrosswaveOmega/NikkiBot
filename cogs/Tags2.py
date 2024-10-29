import asyncio
import base64
from io import BytesIO
from typing import Optional
import discord
from discord.ext import commands, tasks
import re

from discord import app_commands

from sqlitedict import SqliteDict

from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone
import gui
import utility
from utility import MessageTemplates
from bot import (
    TCBot,
    TCGuildTask,
    Guild_Task_Functions,
    StatusEditMessage,
    TC_Cog_Mixin,
)
import numpy as np
from utility.views import BaseView

from cogs.dat_Starboard import Tag


async def is_cyclic_i(start_key):
    visited = set()
    stack = set()

    async def visit(key):
        if key in stack:
            return True
        if key in visited:
            return False
        visited.add(key)
        stack.add(key)

        tag = await Tag.get(key)
        if not tag:
            return False
        text = tag.text
        for word in re.findall(r"\{(.*?)\}", text):
            if await visit(word):
                return True
        stack.remove(key)
        return False

    return await visit(start_key)


async def is_cyclic_mod(start_key, valuestartmain, guildid):
    visited = set()
    stack = set()
    steps = []
    valuestart=valuestartmain
    if not valuestart:
        valuestart=""

    async def visit(key, steps):
        if key in stack:
            print("Key in stack.")
            steps.append(key)
            return True, steps
        if key in visited:
            return False, steps
        visited.add(key)
        stack.add(key)

        tag = await Tag.get(key, guildid)
        if not tag or key != start_key:
            return False, steps
        elif key == start_key:
            text = valuestart
        else:
            text = tag.text
        for word in re.findall(r"\{(.*?)\}", text):
            steps.append(word)
            print(key,word,stack,visited,steps)
            visite,st=await visit(word, steps)
            if  visite:
                print(key in stack, key in visited)
                return True, steps
            steps.pop()
        stack.remove(key)
        return False, steps

    return await visit(start_key, steps)


async def process_text(extracted_text, page):
    result = await page.evaluate(extracted_text)
    return result


async def execute_javascript(tagtext, browser):
    # I don't need to use the javascript library for this.
    # Tag javascript runs with playwright instead as a security precaution.

    result: str = tagtext

    page = await browser.new_page()
    start, end = "<js:{", "}>"
    pattern = r"<js\:\{(.*?)\}>"
    matches = re.finditer(pattern, tagtext)
    for match in reversed(list(matches)):
        print(match)
        extracted_text = match.group(1)
        processed_text = await process_text(extracted_text, page)
        print(processed_text)
        result = result.replace(f"{start}{extracted_text}{end}", processed_text, 1)
    await page.close()
    return result


async def dynamic_tag_get(text, guildid, maxsize=2000):
    result = text
    pattern = re.compile(r"\{(.*?)\}")
    ignorethese=[]
    for i in range(0,10):
        matches = pattern.findall(result)
        if not matches:
            break
        ignorev=False
        for match in matches:
            if match not in ignorethese:
                ignorev=True
            tag = await Tag.get(match, guildid)
            if tag:
                result = result.replace(f"{{{match}}}", tag.text)
            else:
                ignorethese.append(match)
            if len(result) > maxsize:
                result = result[: maxsize - 4] + "..."
                return result
        if not ignorev:
            break
    return result


class TagContentModal(discord.ui.Modal, title="Enter Tag Contents"):
    """Modal for editing tag data"""

    def __init__(self, *args, content=None, key=None, topic=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.followup_input = discord.ui.TextInput(
            label="Enter Content here.",
            max_length=2000,
            default=content,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.followup_input)
        self.topicvalue = discord.ui.TextInput(
            label="Enter category", max_length=128, default=topic, required=True
        )
        self.add_item(self.topicvalue)

    async def on_submit(self, interaction):
        followup = self.followup_input.value
        topic = self.topicvalue.value
        self.done = (followup, "IGNORE ME", topic)
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        self.stop()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        return await super().on_error(interaction, error)


class TagEditView(BaseView):
    """
    View that allows one to edit the work in progress tags.
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
        guild_only=False,
    ):
        super().__init__(user=user, timeout=timeout)
        self.value = False
        self.done = None
        self.content = content
        self.key = key
        self.has_image = has_image
        self.guild_only = guild_only
        self.topic = topic

    def make_embed(self):
        embed = discord.Embed(
            description=f"{self.content}"[:4000],
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="tag category", value=self.topic)

        embed.add_field(name="tag name", value=self.key)
        embed.add_field(
            name="Guild Only",
            value=f"Guild only is set to {self.guild_only}",
            inline=False,
        )
        if not self.is_finished():
            embed.add_field(
                name="timeout",
                value=f"timeout in: {discord.utils.format_dt(self.get_timeout_dt(),'R')}",
                inline=False,
            )
        if self.has_image:
            embed.add_field(
                name="Image Display",
                value="Your real tag will have your uploaded image added, but for efficiency sake a placeholder is used for this preview.",
                inline=False,
            )
            embed.set_image(url="https://picsum.photos/400/200.jpg")
        return embed

    async def on_timeout(self) -> None:
        self.value = "timeout"
        self.stop()

    @discord.ui.button(label="Edit tag", style=discord.ButtonStyle.primary, row=1)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TagContentModal(
            content=self.content, key=self.key, topic=self.topic, timeout=self.timeout
        )
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done:
            c, k, t = modal.done
            self.content = c if c is not None else self.content
            # self.key = k if k is not None else self.key
            self.topic = t if t is not None else self.topic
            self.update_timeout()
            await interaction.edit_original_response(embed=self.make_embed())
            # await self.tag_add_callback(interaction,c,k,t)
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


def convertToBinaryData(file):
    # Convert digital data to binary format
    with BytesIO(file.fp.read()) as f:
        # Read the bytes from the file-like object
        file_bytes = f.read()
    return file_bytes


async def binaryToFile(file_bytes: str, filename: str) -> discord.File:
    # Create a discord.File object
    file = discord.File(BytesIO(file_bytes), filename=filename, spoiler=False)
    return file


class Tags(commands.Cog):
    def __init__(self, bot):
        self.helptext = (
            "This is for Server/User tags. Enter text, retrieve with a shortcut."
        )
        self.bot = bot


    async def tag_edit_autocomplete(self, interaction: discord.Interaction, current: str):
        """
        Autocomplete for tag names
        """
        if interaction.guild:
            tags = await Tag.get_matching_tags_from_user(current, interaction.guild.id, interaction.user.id)
            choices = self._shared_autocomplete_logic(tags, current)

            return choices
        return []

    async def tag_autocomplete(self, interaction: discord.Interaction, current: str):
        """
        Autocomplete for tag names
        """
        if interaction.guild:
            tags = await Tag.get_matching_tags(current, interaction.guild.id)
            choices = self._shared_autocomplete_logic(tags, current)

            return choices
        return []

    def _shared_autocomplete_logic(self, items, current: str):
        """Shared autocomplete logic."""
        search_val = current.lower()
        results = []
        for v in items:
            if len(results) >= 25:
                break
            results.append(app_commands.Choice(name=v.tagname, value=v.tagname))
        return results

    tag_maintenance = app_commands.Group(
        name="tag_maintenance",
        description="For tag moderation",
        default_permissions=discord.Permissions(
            manage_channels=True, manage_messages=True
        ),
        guild_only=True,
    )

    @tag_maintenance.command(
        name="modremove", description="Remove tags with bad content"
    )
    @app_commands.autocomplete(tagname=tag_autocomplete)
    async def modremove(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)

        tag = await Tag.delete_without_user(tagname)
        if not tag:
            await ctx.send("This tag doesn't exist.", ephemeral=True)
            return
        await ctx.send(f"Tag {tagname} was removed successfully.", ephemeral=True)

    tags = app_commands.Group(name="tags", description="Tag commands", guild_only=True)

    @tags.command(name="create", description="create a tag")
    @app_commands.describe(tagname="tagname to add")
    @app_commands.describe(text="text of the tag.")
    async def create(
        self,
        interaction: discord.Interaction,
        tagname: app_commands.Range[str, 2, 128],
        text: app_commands.Range[str, 5, 2000],
        # guild_only: bool = True,
        image: Optional[discord.Attachment] = None,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = await Tag.does_tag_exist(tagname)

        if taglist:
            await MessageTemplates.tag_message(
                ctx,
                f"The tag name `{tagname}` is not available.",
                title="Tag creation error.",
                ephemeral=True,
            )
            return

        # Check for cyclic references in the tag text
        cycle_check, steps = await is_cyclic_mod(tagname, text, ctx.guild.id)
        if cycle_check:
            await MessageTemplates.tag_message(
                ctx,
                f"The text will expand infinitely at keys {str(steps)}.",
                title="Tag creation error.",
                ephemeral=True,
            )
            return

        # Handle image attachment
        bytesv, fname = None, None
        if image:
            file = await image.to_file()
            fname = file.filename
            bytesv = convertToBinaryData(file)

        # Create the interactive view for editing the tag
        view = TagEditView(
            user=interaction.user,
            content=text,
            key=tagname,
            topic="No Topic",
            has_image=True if image is not None else False,
            guild_only=True,
            timeout=10 * 60,
        )
        emb = view.make_embed()
        tmes = await ctx.send(
            "Please apply any edits using the Edit Note button, and press complete when you're satisfied!",
            embed=emb,
            view=view,
            ephemeral=True,
        )

        await view.wait()

        if view.done:
            await tmes.edit(view=None, content="View Closed.")
            if not view.value:
                return

            c, k, t = view.done
            # Recheck for cyclic references with updated content
            cycle_check, steps = await is_cyclic_mod(tagname, c, ctx.guild.id)
            if cycle_check:
                await MessageTemplates.tag_message(
                    ctx,
                    f"The text will expand infinitely at keys {str(steps)}.",
                    title="Tag creation error.",
                    ephemeral=True,
                )
                return

            # Add the new tag to the database
            await Tag.add(
                tagname,
                interaction.user.id,
                c,
                discord.utils.utcnow(),
                ctx.guild.id,
                guildonly=True,
                tag_category=t,
                imb=bytesv,
                imname=fname,
            )

            # Confirm tag creation
            new_tag = await Tag.get(tagname, ctx.guild.id)
            if not new_tag:
                await MessageTemplates.tag_message(
                    ctx,
                    f"Tag {tagname} could not be created. It likely already exists.",
                    title="Tag not created",
                    ephemeral=True,
                )
                return
            await MessageTemplates.tag_message(
                ctx,
                f"Tag {tagname} created, access it with /tags get",
                tag=new_tag.get_dict(),
                title="Tag created",
                ephemeral=True,
            )
        else:
            # Handle user cancellation or timeout
            message = "Cancelled"
            if view.value == "timeout":
                message = "You timed out."
            await tmes.edit(content=message, view=None, embed=view.make_embed())

    @tags.command(name="delete", description="delete a tag")
    @app_commands.autocomplete(tagname=tag_edit_autocomplete)
    @app_commands.describe(tagname="tagname to delete")
    async def delete(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        deleted_tag = await Tag.delete(tagname, interaction.user.id)
        if deleted_tag:
            await MessageTemplates.tag_message(
                ctx,
                f"Tag {tagname} deleted  successfully.",
                tag=None,
                title="Tag deleted.",
                ephemeral=False,
            )
        else:
            await MessageTemplates.tag_message(
                ctx,
                f"You don't have permission to delete this tag.",
                title="Tag delete error.",
            )

    
    @tags.command(name="edit", description="edit a tag")
    @app_commands.autocomplete(tagname=tag_edit_autocomplete)
    @app_commands.describe(tagname="tagname to edit")
    @app_commands.describe(newtext="new text of the tag")
    async def edit(
        self,
        interaction: discord.Interaction,
        tagname: str,
        newtext: Optional[app_commands.Range[str, 5, 2000]] = None,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        new_tag = await Tag.get(tagname, ctx.guild.id)
        if new_tag.user!=interaction.user.id:
            await MessageTemplates.tag_message(
                ctx,
                f"You don't have permission to edit this tag.",
                title="Tag edit error.",
                ephemeral=True,
            )
            return
        text=new_tag.text
        if newtext:
            text=newtext
        view = TagEditView(
            user=interaction.user,
            content=text,
            key=tagname,
            topic=new_tag.tag_category,
            has_image=False,
            guild_only=True,
            timeout=10 * 60,
        )
        emb = view.make_embed()
        tmes = await ctx.send(
            "Please apply any edits using the Edit Note button, and press complete when you're satisfied!",
            embed=emb,
            view=view,
            ephemeral=True,
        )

        await view.wait()

        if view.done:
            await tmes.edit(view=None, content="View Closed.")
            if not view.value:
                return

            c, k, t = view.done
            cycle_check, steps = await is_cyclic_mod(tagname, c, ctx.guild.id)
            if cycle_check:
                await MessageTemplates.tag_message(
                    ctx,
                    f"The text will expand infinitely at keys {str(steps)}.",
                    title="Tag edit error.",
                    ephemeral=False,
                )
                return

            edited_tag = await Tag.edit(tagname, interaction.user.id, newtext=c)
            if edited_tag:
                new_tag = await Tag.get(tagname, ctx.guild.id)
                await MessageTemplates.tag_message(
                    ctx, f"Tag '{tagname}' edited.", tag=new_tag.get_dict(), ephemeral=True
                )
            else:
                await MessageTemplates.tag_message(
                    ctx,
                    f"You don't have permission to edit this tag.",
                    title="Tag edit error.",
                    ephemeral=True,
                )
        else:
            # Handle user cancellation or timeout
            message = "Cancelled"
            if view.value == "timeout":
                message = "You timed out."
            await tmes.edit(content=message, view=None, embed=view.make_embed())


    @tags.command(name="list", description="list all tags")
    async def listtags(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tagdict = await Tag.list_all_cat(ctx.guild.id)
        if not tagdict:
            await MessageTemplates.tag_message(ctx, f"No tags found", ephemeral=True)
            return
        embed_list, e = [], 0
        act=False
        for cat, taglist in tagdict.items():
            e = 0
            embed = discord.Embed(
                title=f"Tags: {cat}, {e+1}", color=discord.Color(0x00787F)
            )
            for name, text in taglist:
                if text:
                    act=True
                    value = text

                    if len(embed.fields) == 10:
                        e += 1
                        embed_list.append(embed)
                        embed = discord.Embed(
                            title=f"Tags: {e+1}", color=discord.Color(0x00787F)
                        )
                        act=False
                    if len(value) > 256:
                        value = value[:256]
                        value += "..."
                    embed.add_field(name=name, value=value, inline=False)
            if act:
                embed_list.append(embed)
        await utility.pages_of_embeds(ctx, embed_list,ephemeral=True)

    @tags.command(name="get", description="get a tag by name")
    @app_commands.autocomplete(tagname=tag_autocomplete)
    @app_commands.describe(tagname="tagname to get")
    async def get(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)

        tag = await Tag.get(tagname, ctx.guild.id)
        if tag:
            text = tag.text
            inc = await Tag.increment(tagname, ctx.guild.id)
            im = None
            if tag.image:
                im = await binaryToFile(tag.image, tag.imfilename)
            output = await dynamic_tag_get(text, ctx.guild.id)
            to_send = f"{output}"
            pattern_exists = bool(re.search(r"<js\:\{(.*?)\}>", to_send))
            if pattern_exists:
                mes = await ctx.send("Javascript running", file=im)
                if not self.bot.browser_on:
                    mes = await mes.edit(content="Activating advanced utility...")
                    await self.bot.open_browser()
                    mes = await mes.edit(content="Javascript running")
                browser = await self.bot.get_browser()

                to_send = await execute_javascript(to_send, browser)
                if len(to_send) > 2000:
                    to_send = to_send[:1996] + "..."

                await mes.edit(content=to_send)
            else:
                if len(to_send) > 2000:
                    to_send = to_send[:1996] + "..."
                await ctx.send(f"{to_send}", file=im)

        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag '{tagname}' not found", title="Tag get error"
            )

    @tags.command(name="info", description="get a tag's info by name")
    @app_commands.autocomplete(tagname=tag_autocomplete)
    @app_commands.describe(tagname="tagname to get")
    async def info(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)

        tag = await Tag.get(tagname, ctx.guild.id)
        if tag:
            await MessageTemplates.tag_message(
                ctx, f"Tag '{tagname}' info.", tag=tag.get_dict(), ephemeral=True
            )
        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag '{tagname}' not found", title="Tag get error", ephemeral=True
            )


async def setup(bot):
    pc = Tags(bot)
    await bot.add_cog(pc)
