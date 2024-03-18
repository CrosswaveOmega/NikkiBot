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


class Global(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        self.globalonly=True
        
    @app_commands.command(name="pingtest", description="ping")
    async def info(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")

async def setup(bot):
    await bot.add_cog(Global(bot))
