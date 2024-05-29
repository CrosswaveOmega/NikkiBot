import asyncio
import json
from typing import Literal, Dict, List
from assets import AssetLookup
import gui
import discord

from datetime import datetime, timedelta
from discord import app_commands
import importlib

from dateutil.rrule import MINUTELY, SU, WEEKLY, rrule
from discord.ext import commands, tasks

from discord.app_commands import Choice

from utility import MessageTemplates, urltomessage
from bot import (
    Guild_Task_Functions,
    StatusEditMessage,
    TC_Cog_Mixin,
    TCBot,
    TCGuildTask,
)

# import datetime
from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands
from .HD2.db import ServerHDProfile
import cogs.HD2 as hd2
from utility.embed_paginator import pages_of_embeds, pages_of_embeds_2
from utility import load_json_with_substitutions
from bot.Tasks import TCTask, TCTaskManager



class HelldiversMathCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        # self.session=aiohttp.ClientSession()
        
    @property
    def apistatus(self)->hd2.ApiStatus:
        return self.bot.get_cog('HelldiversCog').apistatus

    async def campaign_autocomplete(self, interaction:discord.Interaction, current:str):
        '''
        Autocomplete for planet lookup.  Search by either the name or index.
        '''
        items = (l.get_first().planet for l in self.apistatus.campaigns.values())
        search_val = current.lower()
        results = []
        for v in items:
            if len(results) >= 25: break
            if search_val in v.get_name(False).lower():
                results.append(app_commands.Choice(
                    name=v.get_name(False), value=int(v.index)
                ))
        return results
    
    calc = app_commands.Group(name="hd2_calc", description="Commands for mathdiving.")

    @calc.command(name="players_for_dps", description="estimate players needed to get a target dps on a specific planet")
    @app_commands.autocomplete(byplanet=campaign_autocomplete)
    @app_commands.describe(dps="damage per second")
    async def players_for_dps(self, interaction: discord.Interaction,dps:float,byplanet:int):
        ctx: commands.Context = await self.bot.get_context(interaction)

        embeds=[]
        mp_mult=self.apistatus.war.get_first().impactMultiplier
        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            eps=hd2.maths.dps_to_eps(dps,planet.regenPerSecond,mp_mult)
            play,conf=hd2.predict_needed_players(eps,mp_mult)
            embeds.append(
                hd2.create_planet_embed(
                    planet, cstr=None, last=None, stat=self.apistatus
                )
            )
            await ctx.send(f"Need `{play}` players to achieve dps of `{dps}` on {planet.get_name()}."+
                           f"\n standard error `{conf}`.", ephemeral=True)
            #await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)
        else:
            await ctx.send("Planet not found.", ephemeral=True)


    @calc.command(name="dps_to_lph", description="Convert damage per second to liberation per hour.")
    @app_commands.describe(dps="damage per second")
    @app_commands.describe(max_health="Max health of the planet or event.")
    async def dps_to_lph(self, interaction: discord.Interaction,dps:float,max_health:int):
        ctx: commands.Context = await self.bot.get_context(interaction)
        lps=hd2.maths.dps_to_lph(dps,max_health)
        await ctx.send(f"`{dps}` dps is about `{lps}` liberation per hour.", ephemeral=True)







async def setup(bot):
    module_name = "cogs.HD2Math"
    await bot.add_cog(HelldiversMathCog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversMathCog")
