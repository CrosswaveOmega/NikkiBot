import asyncio
import json
from typing import Literal
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
class HelldiversCog(commands.Cog, TC_Cog_Mixin):
    """cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        # self.session=aiohttp.ClientSession()
        
        self.apidata = {}
        self.planets_data=datetime(2024,1,1,0,0,0)
        self.changes = {}
        self.dispatches = None
        self.first_get=True
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
        war = await hd2.GetApiV1War()
        assignments = await hd2.GetApiV1AssignmentsAll()
        campaigns = await hd2.GetApiV1CampaignsAll()
        if 'war' in self.apidata:
            self.changes['war']=(self.apidata['war'],war)
        self.apidata["war"] = war
        last_assign=self.apidata.get('assignments',[])
        last_camp=self.apidata.get('campaigns',[])
        updated_assignments = []
        for assignment in assignments:
            found = False
            for apidata_assignment in last_assign:
                if assignment.id == apidata_assignment.id:
                    updated_assignments.append((apidata_assignment, assignment))
                    found = True
                    break  # Exit the inner loop once a match is found
            if not found:
                updated_assignments.append((assignment, assignment))  # Add to updated_assignments if not found in apidata
        self.changes['assignments'] = updated_assignments
        self.apidata["assignments"] = assignments
        
        updated_campaigns = []
        for campaign in campaigns:
            found = False
            for apidata_campaign in last_camp:
                if campaign.id == apidata_campaign.id:
                    updated_campaigns.append((apidata_campaign, campaign))
                    found = True
                    break  # Exit the inner loop once a match is found
            if not found:
                print(f"not found camp id {campaign.id}")
                updated_campaigns.append((campaign, campaign))  # Add to updated_campaigns if not found in apidata
        self.changes['campaigns'] = updated_campaigns
        self.apidata["campaigns"] = campaigns
        self.dispatches =await hd2.GetApiV1DispatchesAll()
        if self.planets_data and datetime.now() >= self.planets_data + timedelta(hours=2):
            planets=await hd2.GetApiV1PlanetsAll()
            planet_data={}
            for planet in planets:
                planet_data[planet.index]=planet
            self.apidata['planets']=planet_data
            self.planets_data = datetime.now()


    @tasks.loop(minutes=15)
    async def update_api(self):
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
            data = self.changes.get("campaigns", None)
            if not data:
                return await context.send("No result")
            
            
            profile=ServerHDProfile.get(context.guild.id)
            if profile:
                emb=hd2.campaign_view(data)
                emb.timestamp=discord.utils.utcnow()
                target=await urltomessage(profile.overview_message_url,context.bot)
                embs=[emb]
                if self.changes['assignments']:
                    a, b=self.changes['assignments'][0]
                    embs.append(hd2.create_assignment_embed(b,b-a,planets=self.apidata['planets']))
                    
                await target.edit(embeds=embs)
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
                await ctx.send(embed=hd2.create_assignment_embed(this,this-last,planets=self.apidata['planets']))
        else:
            for s in data:
                await ctx.send(embed=hd2.create_assignment_embed(s,planets=self.apidata['planets']))


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
    
    @pc.command(name="planet", description="get data for specific planet(s)")
    @app_commands.describe(byplanet="view specific planet index.")
    async def pstate(self, interaction: discord.Interaction,byplanet:int):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apidata.get("planets", None)
        if not data:
            return await ctx.send("No result")
        embeds=[]
        if byplanet:
            if byplanet in self.apidata['planets']:
                planet= self.apidata['planets'][byplanet]
                embeds.append(hd2.create_planet_embed(planet, cstr='',last=None))

        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)

    @pc.command(name="dispatches", description="get all dispatches.")
    async def dispatch(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.dispatches
        if not data:
            return await ctx.send("No result")
        embeds=[]
        for s in data:
            embeds.append(s.to_embed())
        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)

    @pc.command(name="overview", description="get campaign overview.")
    async def campoverview(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.changes.get("campaigns", None)

        
        if not data:
            return await ctx.send("No result")
        emb=hd2.campaign_view(data)
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
