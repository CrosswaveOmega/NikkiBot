import asyncio
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


def is_cyclic_i(dictionary, start_key):
    """Determine if the passed in key will render a recursive reference somewhere."""
    stack = [(start_key, set(), [start_key])]

    while stack:
        key, visited, steps = stack.pop()

        if key in visited:
            return True

        visited.add(key)
        value = dictionary[key]["text"]
        matches = re.findall(r"\[([^\[\]]+)\]", value)
        keys_to_check = [match for match in matches if match in dictionary["taglist"]]

        for next_key in keys_to_check:
            steps2 = steps.copy()
            steps2.append(next_key)
            stack.append((next_key, visited.copy(), steps2))

    return False


def is_cyclic_mod(dictionary, start_key, valuestart):
    # Check if a key should be added.
    stack = [(start_key, set(), [start_key])]

    while stack:
        key, visited, steps = stack.pop()
        if key in visited:
            return True, steps
        visited.add(key)
        value = ""
        if key == start_key:
            value = valuestart
        else:
            value = dictionary[key]["text"]
        matches = re.findall(r"\[([^\[\]]+)\]", value)
        keys_to_check = [
            match
            for match in matches
            if match in dictionary["taglist"] or match == start_key
        ]
        for next_key in keys_to_check:
            steps2 = steps.copy()
            steps2.append(next_key)
            stack.append((next_key, visited.copy(), steps2))
    return False, 0


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


async def dynamic_tag_get(dictionary, text, maxsize=2000):
    value = text

    gui.gprint(dictionary["taglist"])
    for deep in range(32):
        matches = re.findall(r"\[([^\[\]]+)\]", value)
        keys_to_replace = [match for match in matches if match in dictionary["taglist"]]

        if not keys_to_replace:
            break
        if len(keys_to_replace) <= 0:
            break
        for key_to_replace in keys_to_replace:
            new = dictionary[key_to_replace]["text"]
            if len(new) + len(value) < maxsize:
                value = value.replace("[" + key_to_replace + "]", new)
                await asyncio.sleep(0.01)

    value = value.replace("\\n", "\n")
    return value


class Tags2(commands.Cog):
    def __init__(self, bot):
        self.helptext = (
            "This tag is for user tags.  Enter text, retrieve with a shortcut."
        )
        self.bot = bot
        self.db = SqliteDict("./saveData/tags.sqlite")
        self.userdb = SqliteDict("./saveData/users.sqlite")
        taglist = []
        for i, v in self.db.items():
            if i != "taglist":
                taglist.append(i)
        self.db.update({"taglist": taglist})

    def cog_unload(self):
        self.db.close()
        self.userdb.close()

    tags = app_commands.Group(name="tags", description="Tag commands")

    @tags.command(name="create", description="create a tag")
    @app_commands.describe(tagname="tagname to add")
    @app_commands.describe(text="text of the tag.")
    async def create(self, interaction: discord.Interaction, tagname: str, text: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = self.db.setdefault("taglist", [])
        if tagname in taglist:
            await ctx.send("Tag is already in list.")
            return
        tag = {
            tagname: {
                "tagname": tagname,
                "user": interaction.user.id,
                "text": text,
                "lastupdate": discord.utils.utcnow(),
            }
        }
        cycle_check, steps = is_cyclic_mod(self.db, tagname, text)
        if cycle_check:
            await MessageTemplates.tag_message(
                ctx,
                f"The text will expand infinitely at keys {str(steps)}.",
                tag=tag[tagname],
                title="Tag creation error.",
                ephemeral=False,
            )
            return
        taglist.append(tagname)
        self.db.update(tag)
        self.db.update({"taglist": taglist})
        self.db.commit()
        await MessageTemplates.tag_message(
            ctx,
            f"Tag {tagname} created, access it with /tags get",
            tag=tag[tagname],
            title="Tag created",
            ephemeral=False,
        )

    @tags.command(name="delete", description="delete a tag")
    @app_commands.describe(tagname="tagname to delete")
    async def delete(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = self.db.setdefault("taglist", [])
        if tagname not in taglist:
            await ctx.send("Tag not found.")
            return
        tag = self.db.get(tagname, {})
        if tag.get("user") == interaction.user.id:
            tag = self.db.pop(tagname)
            taglist.remove(tagname)
            self.db.commit()
            await MessageTemplates.tag_message(
                ctx,
                f"Tag {tagname} Deleted, access it with /tags get",
                tag=tag,
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
    async def edit(self, interaction: discord.Interaction, tagname: str, newtext: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})

        if tag:
            if tag.get("user") == interaction.user.id:
                cycle_check, steps = is_cyclic_mod(self.db, tagname, newtext)
                if cycle_check:
                    await MessageTemplates.tag_message(
                        ctx,
                        f"The text will expand infinitely at keys {str(steps)}.",
                        tag=tag,
                        title="Tag edit error.",
                        ephemeral=False,
                    )
                    return
                tag["text"] = newtext
                tag["lastupdate"] = discord.utils.utcnow()
                self.db[tagname] = tag
                self.db.commit()
                await MessageTemplates.tag_message(
                    ctx, f"Tag '{tagname}' edited.", tag=tag
                )
            else:
                await MessageTemplates.tag_message(
                    ctx,
                    f"You don't have permission to edit this tag.",
                    title="Tag edit error.",
                )
        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag not found", title="Tag edit error."
            )

    @tags.command(name="list", description="list all tags")
    async def listtags(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = self.db.get("taglist")
        if taglist:
            # Loop through the dictionary and create an Embed object for each set of key-value pairs
            embed_list, e = [], 0
            for t in taglist:
                key, value = t, self.db.get(t)["text"]
                # Check if the Embed list is empty or if the last Embed object has 4 fields already
                if not embed_list or len(embed_list[-1].fields) == 4:
                    # If so, create a new Embed object
                    embed = discord.Embed(
                        title=f"Tags: {e + 1}", color=discord.Color(0x00787F)
                    )
                    # Add the first field to the new Embed object
                    if len(value) > 1010:
                        value = value[:1010]
                        value += "..."

                    embed.add_field(name=key, value=value, inline=False)
                    # Add the new Embed object to the list
                    embed_list.append(embed)
                    e += 1
                else:
                    # If not, add the current key-value pair as a new field to the last Embed object
                    embed_list[-1].add_field(name=key, value=value, inline=False)

            await utility.pages_of_embeds(ctx, embed_list)

        else:
            await MessageTemplates.tag_message(ctx, f"No tags found")

    @tags.command(name="get", description="get a tag")
    @app_commands.describe(tagname="tagname to get")
    async def get(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)

        tag = self.db.get(tagname, {})
        if tag:
            if is_cyclic_i(self.db, tagname):
                await ctx.send(f"WARNING!  Tag {tagname} is cyclic!")
                return
            text = tag.get("text")
            output = await dynamic_tag_get(self.db, text)
            to_send = f"{output}"
            pattern_exists = bool(re.search(r"<js\:\{(.*?)\}>", to_send))
            if pattern_exists:
                mes = await ctx.send("Javascript running")
                if not self.bot.browser_on:
                    mes = await mes.edit(content="Activating advanced utility...")
                    await self.bot.open_browser()
                    mes = await mes.edit(content="Javascript running")
                browser = await self.bot.get_browser()

                to_send = await execute_javascript(to_send, browser)
                if len(to_send) > 2000:
                    to_send = to_send[:1950] + "tag size limit."

                await mes.edit(content=to_send)
            else:
                if len(to_send) > 2000:
                    to_send = to_send[:1950] + "tag size limit."
                await ctx.send(to_send)
        else:
            await MessageTemplates.tag_message(ctx, f"Tag not found.")

    @tags.command(name="getraw", description="get a tag's raw text")
    @app_commands.describe(tagname="tagname to get")
    async def getraw(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})
        if tag:
            if is_cyclic_i(self.db, tagname):
                await ctx.send(f"WARNING!  Tag {tagname} is cyclic!")
                return
            text = tag.get("text")
            output = text
            await MessageTemplates.tag_message(
                ctx, f"Displaying raw tag text.", tag=tag, title="Raw Tag Text."
            )

        else:
            await MessageTemplates.tag_message(ctx, f"Tag not found.")

    @commands.command()
    async def tagcycletest(self, ctx):
        """Test the tag render."""
        cases = [
            {
                "taglist": ["A", "B", "C", "D"],
                "A": {"text": "[B] [C] [D]", "out": False},
                "B": {"text": "[C]", "out": False},
                "C": {"text": "[D]", "out": False},
                "D": {"text": "", "out": False},
            },
            {
                "taglist": ["A", "B", "C", "D", "E", "F", "G"],
                "A": {"text": "[B] [C] [D]", "out": False},
                "B": {"text": "[C]", "out": False},
                "C": {"text": "[D]", "out": False},
                "D": {"text": "", "out": False},
                "G": {"text": "[E]", "out": True},
                "E": {"text": "[F]", "out": True},
                "F": {"text": "[E]", "out": True},
            },
        ]
        for emdata, data in enumerate(cases):
            await ctx.send(f"Pass number {emdata}")
            assert is_cyclic_mod(data, "A", {"text": "[B]"}) == False
            assert is_cyclic_mod(data, "G", {"text": "[G]"}) == True
            for i, v in data.items():
                if i == "taglist":
                    continue
                text = v["text"]
                gui.dprint(i, v)
                result = is_cyclic_i(data, i)
                assert result == v["out"]
            await ctx.send("pass complete")


async def setup(bot):
    pass
    # pc = Tags2(bot)
    # await bot.add_cog(pc)
