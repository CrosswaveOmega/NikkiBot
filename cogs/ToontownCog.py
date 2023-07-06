from typing import Literal
import discord
import operator
import io
import json
import aiohttp
import asyncio
import re
#import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU

from datetime import datetime, time, timedelta
import time
from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import MessageTemplates, RRuleView, formatutil, seconds_to_time_string, urltomessage
from utility.embed_paginator import pages_of_embeds
from bot import TCBot,TC_Cog_Mixin, super_context_menu
import purgpt
from database import DatabaseSingleton
from gptfunctionutil import *
import purgpt.error
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
import gui
async def api_get(url):
    headers = {
        'user-agent': 'NikkiBot/1.0.0'
    }

    
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession() as session:
        print(f"https://corporateclash.net/api/v1/districts.js")
        try:
            async with session.get(f"{url}", headers=headers, timeout=timeout) as response:
                if response.content_type== "application/json":
                    print(response)
                    result = await response.json()
                    return result
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                raise e
        except aiohttp.ClientError as e:
            raise e


    
class ToonTownCog(commands.Cog, TC_Cog_Mixin):
    """For Timers."""
    def __init__(self, bot):
        self.helptext="For Toontown Corporate Clash Api."
        self.bot=bot


    @AILibFunction(name='toontown_district',description='retrieve all connected toontown districts', required=['comment'])
    @LibParam(comment='An interesting, amusing remark.')
    @commands.command(name='toontown_districts',description='Get toontown districts',extras={})
    async def toontown_district(self,ctx:commands.Context,comment:str="Here are the districts."):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        now=datetime.now()
        result=await api_get('https://corporateclash.net/api/v1/districts.js')
        await ctx.send(f"{comment}\nToontown Corporate Clash Districts Count:\n{len(result)}")
        embeds=[]
        for data in result:

            # Create an empty embed
            print(data)
            embed = discord.Embed(title=data["name"])
            embed.set_author(name="Toontown Corporate Clash", icon_url=bot.user.avatar)
            # Set the title
            embed.add_field(name="Online", value=data["online"])
            
            embed.add_field(name="Population", value=data["population"])
            # Set the timestamp from the 'last_update' value
            timestamp = datetime.fromtimestamp(data["last_update"])
            embed.timestamp = timestamp

            embed.add_field(name="Invasion", value=data["invasion_online"])
            # Add fields based on condition
            
            embed.add_field(name="Cogs Attacking", value=data["cogs_attacking"])
            if data["invasion_online"]:
                embed.add_field(name="Count Defeated", value=data["count_defeated"])
                embed.add_field(name="Count Total", value=data["count_total"])
                embed.add_field(name="Remaining Time", value=data["remaining_time"])

                        # Add other fields
            embeds.append(embed)
            if len(embeds)>10:
                await ctx.send(embeds=embeds)
                embeds=[]
        if embeds:
            await ctx.send(embeds=embeds)
            


    

        



async def setup(bot):
    await bot.add_cog(ToonTownCog(bot))
