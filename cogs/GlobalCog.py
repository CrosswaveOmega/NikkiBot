from typing import Literal
import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv

# import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU

from datetime import datetime, timedelta
import time
from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook, ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import MessageTemplates, RRuleView, formatutil
from utility.embed_paginator import pages_of_embeds
from utility import WebhookMessageWrapper as web
from bot import TC_Cog_Mixin, super_context_menu, TCGuildTask, TCTaskManager
import cogs.ResearchAgent as ra
from discord.app_commands import checks, MissingPermissions

async def owneronly(interaction: discord.Interaction):
    return await interaction.client.is_owner(interaction.user)

class Global(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        self.globalonly=True

    @app_commands.command(name="search", description="search the interwebs.")
    @app_commands.describe(query="Query to search google with.")
    async def websearch(self, interaction: discord.Interaction, query:str) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> Searching")
        results = ra.tools.google_search(ctx.bot, query, 7)
        allstr = ""
        emb = discord.Embed(title="Search results", description='loading.')
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
            outputthis += f"+ **Title: {r['title']}**\n **Link:**{r['link']}\n **Snippit:**\n{indent_string(desc,1)}"
        await mess.edit(embed=emb)

    @app_commands.command(name="supersearch", description="use db search.")
    @app_commands.describe(query="Query to search DB for")

    async def doc_talk(self, interaction: discord.Interaction, query:str) -> None:
        """get bot info for this server"""
        owner=await interaction.client.is_owner(interaction.user)
        if not owner:
            await interaction.response.send_message("This command is owner only.")
            return
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> Searching")
        try:
            ans,source,_=await ra.actions.research_op(query, 9)
            emb = discord.Embed(description=ans)
            emb.add_field(name="source", value=str(source)[:1000], inline=False)
            await mess.edit(content=None,embed=emb)
        except Exception as e:
            await ctx.send("something went wrong...")



    @app_commands.command(name="pingtest", description="ping")
    async def info(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")

    

async def setup(bot):
    await bot.add_cog(Global(bot))
