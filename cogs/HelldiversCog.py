import asyncio
import json
from typing import Literal
import gui
import discord
from discord import app_commands
import importlib
from discord.ext import commands, tasks

# import datetime
from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands
from .HD2.hdapi import call_api, human_format
import cogs.HD2 as hd2
from utility.embed_paginator import pages_of_embeds
class HelldiversCog(commands.Cog, TC_Cog_Mixin):
    """cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        # self.session=aiohttp.ClientSession()
        self.apidata = {}
        self.changes = {}
        self.first_get=True

        self.update_api.start()

    def cog_unload(self):
        self.update_api.cancel()

    async def update_data(self):
        war = await hd2.GetApiV1War()
        assignments = await hd2.GetApiV1AssignmentsAll()
        campaigns = await hd2.GetApiV1CampaignsAll()
        if 'war' in self.apidata:
            self.changes['war']=(self.apidata['war'],war)
        self.apidata["war"] = war
        if 'assignments' in self.apidata:
            self.changes['assignments'] = [(self.apidata["assignments"][i], a) for i, a in enumerate(assignments) if a.id == self.apidata["assignments"][i].id]
        self.apidata["assignments"] = assignments
        if 'campaigns' in self.apidata:
            self.changes['campaigns'] = [(self.apidata["campaigns"][j], c) for j, c in enumerate(campaigns) if c.id == self.apidata["campaigns"][j].id]
        self.apidata["campaigns"] = campaigns

    @tasks.loop(minutes=15)
    async def update_api(self):
        try:
            print("updating war")
            await self.update_data()
            if self.first_get:
                print("getting update data.")
                await asyncio.sleep(11)
                await self.update_data()
                print("all data retrieved..")
                self.first_get=False
        except Exception as e:
            await self.bot.send_error(e, f"Message update cleanup error.")
            gui.gprint(str(e))
    pc = app_commands.Group(name="hd2", description="Commands for Helldivers 2.")

    @pc.command(name="war", description="get war state.")
    async def warstat(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apidata.get("war", None)
        if not data:
            return await ctx.send("No result")

        if 'war' in self.changes:
            last, this =self.changes['war']
            await ctx.send(embed=hd2.create_war_embed(this,last))
        else:
            await ctx.send(embed=hd2.create_war_embed(data))

    @pc.command(name="assign", description="get assignment state.")
    async def assignstate(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apidata.get("assignments", None)
        if not data:
            return await ctx.send("No result")

        if 'assignments' in self.changes:
            for last,this in self.changes['assignments']:
                await ctx.send(embed=hd2.create_assignment_embed(this,this-last))
        else:
            for s in data:
                await ctx.send(embed=hd2.create_assignment_embed(s))


    @pc.command(name="campaigns", description="get campaign state.")
    async def cstate(self, interaction: discord.Interaction,filter:Literal[0,2,3]=0,byplanet:int=0):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.changes.get("campaigns", None)
        if not data:
            return await ctx.send("No result")
        embeds=[]
        for last,camp in self.changes['campaigns']:
            diff=camp.planet-camp.planet
            if last!=None:
                diff=camp.planet-last.planet
            if byplanet!=0:
                if camp.planet.index==byplanet:
                    
                    cstr = hd2.create_campaign_str(camp)
                    embeds.append(hd2.create_planet_embed(camp.planet, cstr=cstr,last=diff))
            else:
                if filter==0:
                    cstr = hd2.create_campaign_str(camp)
                    embeds.append(hd2.create_planet_embed(camp.planet, cstr=cstr,last=diff))
                elif filter==2:
                    evtcheck=camp['planet']['event']
                    if evtcheck:
                        evtcheck=evtcheck['faction']=='Terminids'
                    if camp['planet']['currentOwner']=='Terminids' or evtcheck:
                        cstr = hd2.create_campaign_str(camp)
                        embeds.append(hd2.create_planet_embed(camp.planet, cstr=cstr,last=diff))
                elif filter==3:
                    evtcheck=camp['planet']['event']
                    if evtcheck:
                        evtcheck=evtcheck['faction']=='Automaton'
                    if camp['planet']['currentOwner']=='Automaton' or evtcheck:
                        cstr = hd2.create_campaign_str(camp)
                        embeds.append(hd2.create_planet_embed(camp.planet, cstr=cstr,last=diff))
        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)


async def setup(bot):
    module_name = "cogs.HD2"
    try:
        importlib.reload(hd2)
        print(f"{module_name} reloaded successfully.")
    except ImportError:
        print(f"Failed to reload {module_name}.")
    await bot.add_cog(HelldiversCog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversCog")

