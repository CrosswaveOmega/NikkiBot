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
        for word in re.findall(r'\{(.*?)\}', text):
            if await visit(word):
                return True
        stack.remove(key)
        return False

    return await visit(start_key)

async def is_cyclic_mod(start_key, valuestart,guildid):
    visited = set()
    stack = set()
    steps = []

    async def visit(key, steps):
        if key in stack:
            steps.append(key)
            return True, steps
        if key in visited:
            return False, steps
        visited.add(key)
        stack.add(key)

        tag = await Tag.get(key,guildid)
        if not tag and key!=start_key:
            return False, steps
        elif key==start_key:
            text=valuestart
        else:
            text = tag.text
        for word in re.findall(r'\{(.*?)\}', text):
            steps.append(word)
            if await visit(word, steps):
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
        extracted_text = match.group(1)
        processed_text = await process_text(extracted_text, page)
        result = result.replace(f"{start}{extracted_text}{end}", processed_text, 1)
    await page.close()
    return result

async def dynamic_tag_get(text, guildid,maxsize=2000):
    result = text
    pattern = re.compile(r'\{(.*?)\}')
    while True:
        matches = pattern.findall(result)
        if not matches:
            break
        for match in matches:
            tag = await Tag.get(match,guildid)
            if tag:
                result = result.replace(f'{{{match}}}', tag.text)
            if len(result) > maxsize:
                result = result[:maxsize-4] + '...'
                return result
    return result

async def file_to_data_uri(file: discord.File) -> str:
    # Read the bytes from the file
    with BytesIO(file.fp.read()) as f:
        # Read the bytes from the file-like object
        file_bytes = f.read()
    # Base64 encode the bytes
    base64_encoded = base64.b64encode(file_bytes).decode("ascii")
    # Construct the data URI
    data_uri = f'data:{"image"};base64,{base64_encoded}'
    return data_uri

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
        self.helptext = "This is for Server/User tags. Enter text, retrieve with a shortcut."
        self.bot = bot

    async def tag_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """
        Autocomplete for tag names
        """
        if interaction.guild:
            tags = await Tag.get_matching_tags(current,interaction.guild.id)
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
            
            results.append(
                app_commands.Choice(name=v.tagname, value=v.tagname)
            )
        return results

    tags = app_commands.Group(name="tags", description="Tag commands")

    @tags.command(name="create", description="create a tag")
    @app_commands.describe(tagname="tagname to add")
    @app_commands.describe(text="text of the tag.", guild_only="If this tag should only work in this guild")
    async def create(self, interaction: discord.Interaction, tagname: str, text: str, guild_only:bool=True,
        image: Optional[discord.Attachment] = None,):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = await Tag.does_tag_exist(tagname)
        if taglist:
            await ctx.send("The desired tag name is not available.")
            return

        cycle_check, steps = await is_cyclic_mod(tagname, text,ctx.guild.id)
        if cycle_check:
            await MessageTemplates.tag_message(
                ctx,
                f"The text will expand infinitely at keys {str(steps)}.",
                title="Tag creation error.",
                ephemeral=False,
            )
            return
        bytes, fname=None,None
        if image:
            file=await image.to_file()
            fname=file.filename
            bytes=convertToBinaryData(file)
        await Tag.add(tagname, interaction.user.id, text, discord.utils.utcnow(),ctx.guild.id,guild_only,imb=bytes,imname=fname)
        new_tag=await Tag.get(tagname,ctx.guild.id)
        if not new_tag:
            await MessageTemplates.tag_message(
                ctx,
                f"Tag {tagname} could not be created.  It likely already exists.",
                title="Tag not created",
                ephemeral=False,
            )
            return
        await MessageTemplates.tag_message(
            ctx,
            f"Tag {tagname} created, access it with /tags get",
            tag={"tagname": new_tag.tagname, "user": new_tag.user, "text": new_tag.text, "lastupdate": new_tag.lastupdate, "filename":new_tag.imfilename,"guild_only":new_tag.guild_only},
            title="Tag created",
            ephemeral=False,
        )

    @tags.command(name="delete", description="delete a tag")
    @app_commands.describe(tagname="tagname to delete")
    async def delete(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        deleted_tag = await Tag.delete(tagname, interaction.user.id)
        if deleted_tag:
            await MessageTemplates.tag_message(
                ctx,
                f"Tag {tagname} Deleted, access it with /tags get",
                tag={"tagname": deleted_tag.tagname, "user": deleted_tag.user, "text": deleted_tag.text, "lastupdate": deleted_tag.lastupdate},
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
    @app_commands.describe(tagname="tagname to edit")
    @app_commands.describe(newtext="new text of the tag")
    async def edit(self, interaction: discord.Interaction, tagname: str, newtext: Optional[str]=None,  guild_only:Optional[bool]=None,):
        ctx: commands.Context = await self.bot.get_context(interaction)
        cycle_check, steps = await is_cyclic_mod(tagname, newtext,ctx.guild.id)
        if cycle_check:
            await MessageTemplates.tag_message(
                ctx,
                f"The text will expand infinitely at keys {str(steps)}.",
                title="Tag edit error.",
                ephemeral=False,
            )
            return

        edited_tag = await Tag.edit(tagname, interaction.user.id, newtext,guild_only)
        if edited_tag:
            await MessageTemplates.tag_message(
                ctx, f"Tag '{tagname}' edited.", tag={"tagname": edited_tag.tagname, "user": edited_tag.user, "text": edited_tag.text, "lastupdate": edited_tag.lastupdate,"guild_only":edited_tag.guild_only}
            )
        else:
            await MessageTemplates.tag_message(
                ctx,
                f"You don't have permission to edit this tag.",
                title="Tag edit error.",
            )

    @tags.command(name="list", description="list all tags")
    async def listtags(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = await Tag.list_all(ctx.guild.id)
        if taglist:
            embed_list, e = [], 0
            for t in taglist:
                key, val = t, await Tag.get(t,ctx.guild.id)
                if val:
                    value = val.text
                    if not embed_list or len(embed_list[-1].fields) == 4:
                        embed = discord.Embed(
                            title=f"Tags: {e+1}", color=discord.Color(0x00787F)
                        )
                        if len(value) > 1010:
                            value = value[:1010]
                            value += "..."
                        embed.add_field(name=key, value=value, inline=False)
                        embed_list.append(embed)
                        e += 1
                    else:
                        embed_list[-1].add_field(name=key, value=value, inline=False)

            await utility.pages_of_embeds(ctx, embed_list)
        else:
            await MessageTemplates.tag_message(ctx, f"No tags found")


    
    @tags.command(name="get", description="get a tag by name")
    @app_commands.autocomplete(tagname=tag_autocomplete)
    @app_commands.describe(tagname="tagname to get")
    async def get(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)

        tag = await Tag.get(tagname,ctx.guild.id)
        if tag:
            text = tag.text
            im=None
            if tag.image:
                im=await binaryToFile(tag.image,tag.imfilename)
            output = await dynamic_tag_get(text,ctx.guild.id)
            to_send = f"{output}"
            pattern_exists = bool(re.search(r"<js\:\{(.*?)\}>", to_send))
            if pattern_exists:
                mes = await ctx.send("Javascript running",file=im)
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
                await ctx.send(f"{to_send}",file=im)

        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag '{tagname}' not found", title="Tag get error"
            )


async def setup(bot):
    pc = Tags(bot)
    await bot.add_cog(pc)
