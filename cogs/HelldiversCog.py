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
from utility.embed_paginator import pages_of_embeds
from utility import load_json_with_substitutions 

class HelldiversCog(commands.Cog, TC_Cog_Mixin):
    """cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        # self.session=aiohttp.ClientSession()
        hdoverride=hd2.APIConfig()
        hdoverride.client_name=bot.keys.get("hd2cli")
        self.apistatus=hd2.ApiStatus(client=hdoverride)
        
        self.hd2=load_json_with_substitutions('./assets/json','flavor.json',{}).get('hd2',{})
        self.api_up=True
        #self.profiles=ServerHDProfile.get_entries_with_overview_message_id()
        
        Guild_Task_Functions.add_task_function("UPDATEOVERVIEW", self.gtask_update)
        self.update_api.start()

    def server_profile_field_ext(self, guild: discord.Guild):
        """
        Create a dictionary representing the helldiver overview panel.
        """
        profile = ServerHDProfile.get(guild.id)
        if not profile:
            return None
        if profile.overview_message_url:
            field = {"name": "Helldiver Overview", "value": f'[Overview]({profile.overview_message_url})'}
            return field
        return None

    def cog_unload(self):
        self.update_api.cancel()
        
        Guild_Task_Functions.remove_task_function("UPDATEOVERVIEW")

    async def update_data(self):
        if self.api_up:
            await self.apistatus.update_data()
        return


    @tasks.loop(minutes=15)
    async def update_api(self):
        
        self.hd2=load_json_with_substitutions('./assets/json','flavor.json',{}).get('hd2',{})
        try:
            print("updating war")
            await self.update_data()
        except Exception as e:
            await self.bot.send_error(e, f"Message update cleanup error.")
            gui.gprint(str(e))

    async def gtask_update(self, source_message:discord.Message=None):
        """
        Guild task that updates the overview message.
        """
        if not source_message:
            return None
        context = await self.bot.get_context(source_message)

        #await context.channel.send("Greetings from GTASK.")
        try:

            
            
            profile=ServerHDProfile.get(context.guild.id)
            if profile:
                
                target=await urltomessage(profile.overview_message_url,context.bot)
                if self.api_up is False:
                    await target.edit(content="WARNING, COMMS ARE DOWN!")
                    return
                emb=hd2.campaign_view(self.apistatus,self.hd2)
                emb.timestamp=discord.utils.utcnow()
                embs=[emb]
                if self.apistatus.assignments:
                    for i, assignment in self.apistatus.assignments.items():
                        b,a=assignment.get_first_change()
                        embs.append(hd2.create_assignment_embed(b,b-a,planets=self.apistatus.planets))
                        
                await target.edit(content="Current game status.", embeds=embs)
                return "OK"
        except Exception as e:
            er = MessageTemplates.get_error_embed(
                title=f"Error with AUTO", description=f"{str(e)}"
            )
            await source_message.channel.send(embed=er)
            raise e
        
    @commands.is_owner()
    @commands.command(name="load_now")
    async def load_now(self, ctx: commands.Context):
        await self.update_data()
        await ctx.send("force loaded api data now.")

    @commands.is_owner()
    @commands.command(name="api_down")
    async def api_off(self, ctx: commands.Context):
        self.api_up=not self.api_up
        await ctx.send(f"Api set is {self.api_up}")

    pcs = app_commands.Group(name="hd2setup", description="Commands for Helldivers 2 setup.", guild_only=True, default_permissions=discord.Permissions(manage_messages=True, manage_channels=True))
    @pcs.command(name="make_overview",description="Setup a constantly updating message ")
    async def overview_make(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        profile=ServerHDProfile.get_or_new(ctx.guild.id)
        guild=ctx.guild
        task_name="UPDATEOVERVIEW"
        autochannel=ctx.channel
        
        target_message=await autochannel.send("Overview_message")
        old = TCGuildTask.get(guild.id, task_name)
        url=target_message.jump_url
        profile.update(overview_message_url=url)
        if not old:
            now=datetime.now()
            start_date = datetime(2023, 1, 1, now.hour, now.minute-15)
            robj = rrule(freq=MINUTELY, interval=15, dtstart=start_date)

            new = TCGuildTask.add_guild_task(guild.id, task_name, target_message, robj,True)
            new.to_task(ctx.bot)

            result = f"Overview message set.  every 15 minutes, this message will update with the latest galactic status.  Please don't delete it unless you want to stop."
            await ctx.send(result)
        else:
            old.target_channel_id = autochannel.id

            target_message = await autochannel.send("**ALTERING AUTO CHANNEL...**")
            old.target_message_url = target_message.jump_url
            self.bot.database.commit()
            result = f"Changed the dashboard channel to <#{autochannel.id}>"
            await ctx.send(result)




    pc = app_commands.Group(name="hd2", description="Commands for Helldivers 2.")

    @pc.command(name="war", description="get war state.")
    async def warstat(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus.war:
            return await ctx.send("No result")
        this,last=self.apistatus.war.get_first_change()
        await ctx.send(embed=hd2.create_war_embed(this,last))
        return


    @pc.command(name="assign", description="get assignment state.")
    async def assignstate(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus.assignments:
            return await ctx.send("No result")
        
        for ind, key in self.apistatus.assignments.items():
            this,last=key.get_first_change()
            await ctx.send(embed=hd2.create_assignment_embed(this,this-last,planets=self.apistatus.planets))



    @pc.command(name="campaigns", description="get campaign state.")
    @app_commands.choices(
        filter=[  # param name
            Choice(name="View campaigns for all planets", value=0),
            Choice(name="View campaigns for bug planets only", value=2),
            
            Choice(name="View campaigns for bot planets", value=3),
        ]
    )
    @app_commands.describe(byplanet="view campaign for this specific planet index.")
    async def cstate(self, interaction: discord.Interaction,filter:Literal[0,2,3]=0,byplanet:int=0):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus.campaigns:
            return await ctx.send("No result")
        embeds=[]
        
        for ind, key in self.apistatus.campaigns.items():
            camp,last=key.get_first_change()
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
    
    @pc.command(name="planet", description="get data for specific planet(s)")
    @app_commands.describe(byplanet="view specific planet index.")
    async def pstate(self, interaction: discord.Interaction,byplanet:int):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.planets
        if not data:
            return await ctx.send("No result")
        embeds=[]
        if byplanet:
            if byplanet in self.apistatus.planets:
                planet= self.apistatus.planets[byplanet]
                embeds.append(hd2.create_planet_embed(planet, cstr='',last=None))

        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)

    @pc.command(name="dispatches", description="get all dispatches.")
    async def dispatch(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.dispatches
        if not data:
            return await ctx.send("No result")
        embeds=[]
        for s in data:
            embeds.append(s.to_embed())
        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)

    @pc.command(name="overview", description="get campaign overview.")
    async def campoverview(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.campaigns

        
        if not data:
            return await ctx.send("No result")
        emb=hd2.campaign_view(self.apistatus,self.hd2)
        await ctx.send(embed=emb)


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

