import gui
from typing import Any, Coroutine
import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv
#import datetime
from datetime import datetime, timedelta

from queue import Queue

from discord.ext import commands, tasks
from discord.interactions import Interaction
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import serverAdmin, serverOwner, MessageTemplates
from utility.embed_paginator import pages_of_embeds
from bot import TC_Cog_Mixin, super_context_menu



        
class AutomodCog(commands.Cog, TC_Cog_Mixin):
    """Commands for some games.  Eventually."""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot

    @app_commands.command(name="automodplaceholder", description="placeholder for future automod config commands.")
    async def automod(self, interaction: discord.Interaction) -> None:
        ctx: commands.Context = await self.bot.get_context(interaction)
        await ctx.send("There's a badge for this.")
    




async def setup(bot):
    await bot.add_cog(AutomodCog(bot))
