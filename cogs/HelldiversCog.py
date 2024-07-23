import asyncio
import io
import json
from typing import Literal, Dict, List
from assetloader import AssetLookup
import gui
import discord

from datetime import datetime, timedelta, timezone
from discord import app_commands
import importlib

from dateutil.rrule import MINUTELY, DAILY, SU, WEEKLY, rrule
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
import re
import cogs.HD2 as hd2
from utility.embed_paginator import pages_of_embeds, pages_of_embeds_2
from utility import load_json_with_substitutions
from bot.Tasks import TCTask, TCTaskManager


class HD2OverviewView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.my_count = {}
        self.cog: "HelldiversCog" = cog

    async def callback(self, interaction, button):
        user = interaction.user
        label = button.label
        if not str(user.id) in self.my_count:
            self.my_count[str(user.id)] = 0
        self.my_count[str(user.id)] += 1
        await interaction.response.send_message(
            f"You are {user.name}, this is {label}, and you have pressed this button {self.my_count[str(user.id)]} times.",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            f"Oops! Something went wrong, {str(error)}", ephemeral=True
        )

    @discord.ui.button(
        label="War Stats",
        style=discord.ButtonStyle.red,
        custom_id="hd_persistent_view:war",
    )
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        this, last = self.cog.apistatus.war.get_first_change()
        await interaction.response.send_message(
            f"Embed",
            embed=(hd2.create_war_embed(self.cog.apistatus)),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Planets",
        style=discord.ButtonStyle.green,
        custom_id="hd_persistent_view:campaigns",
    )
    async def view_planets(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embeds = []

        for ind, key in self.cog.apistatus.campaigns.items():
            camp, last = key.get_first_change()
            diff = camp - last
            embeds.append(
                hd2.create_planet_embed(
                    camp.planet, cstr=camp, last=diff.planet, stat=self.cog.apistatus
                )
            )
        pcc, _ = await pages_of_embeds_2(True, embeds, show_page_nums=False)
        but = hd2.ListButtons(callbacker=pcc)
        await interaction.response.send_message(
            embed=pcc.make_embed(), view=but, ephemeral=True
        )

    @discord.ui.button(
        label="Estimate",
        style=discord.ButtonStyle.blurple,
        custom_id="hd_persistent_view:blue",
    )
    async def show_estimate(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        est = self.cog.apistatus.estimates()
        print(est)
        title = "Galactic War Forecast"
        embed = discord.Embed(title=f"{title}")
        embeds = [embed]
        total_size = len(title)

        for name, val in est:
            total_size += len(name)
            for v in val:
                if total_size + len(v) >= 5800:
                    embed = discord.Embed(title=f"{title}")
                    embeds.append(embed)
                    total_size = len(title) + len(name) + len(v)
                else:
                    total_size += len(v)
                embed.add_field(name=name, value=v[:1024], inline=False)
        pcc, _ = await pages_of_embeds_2(True, embeds, show_page_nums=False)
        but = hd2.ListButtons(callbacker=pcc)
        await interaction.response.send_message(
            embed=pcc.make_embed(), view=but, ephemeral=True
        )

    @discord.ui.button(
        label="View Map",
        style=discord.ButtonStyle.grey,
        custom_id="hd_persistent_view:grey",
    )
    async def map(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"https://helldiverscompanion.com/",
            ephemeral=True,
        )
        # await self.callback(interaction, button)


class HelldiversCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        # self.session=aiohttp.ClientSession()
        hdoverride = hd2.APIConfig()
        self.img = None
        hdoverride.client_name = bot.keys.get("hd2cli")
        self.apistatus = hd2.ApiStatus(client=hdoverride)

        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )
        self.api_up = True

        Guild_Task_Functions.add_task_function("UPDATEOVERVIEW", self.gtask_update)
        Guild_Task_Functions.add_task_function("WARSTATUS", self.gtask_map)
        snap = hd2.load_from_json("./saveData/hd2_snapshot.json")
        self.bot.add_view(HD2OverviewView(self))
        if snap:
            try:
                new_cls = hd2.ApiStatus.from_dict(snap, client=hdoverride)
                self.apistatus = new_cls
            except Exception as e:
                print(e)
                self.bot.logs.exception(e)
        nowd = datetime.now()
        st = datetime(
            nowd.year, nowd.month, nowd.day, nowd.hour, int(nowd.minute / 15) * 15
        )
        robj = rrule(freq=MINUTELY, interval=15, dtstart=st)
        if not TCTaskManager.does_task_exist("SuperEarthStatus"):
            self.tc_task = TCTask("SuperEarthStatus", robj, robj.after(st))
            self.tc_task.assign_wrapper(self.update_api)
        # self.update_api.start()

    def server_profile_field_ext(self, guild: discord.Guild):
        """
        Create a dictionary representing the helldiver overview panel.
        """
        profile = ServerHDProfile.get(guild.id)
        if not profile:
            return None
        if profile.overview_message_url:
            field = {
                "name": "Helldiver Overview",
                "value": f"[Overview]({profile.overview_message_url})",
            }
            return field
        return None

    def cog_unload(self):
        if self.img:
            self.img = None
        hd2.save_to_json(self.apistatus, "./saveData/hd2_snapshot.json")
        TCTaskManager.remove_task("SuperEarthStatus")
        Guild_Task_Functions.remove_task_function("UPDATEOVERVIEW")

    async def update_data(self):
        if self.api_up:
            await self.apistatus.update_data()
            hd2.save_to_json(self.apistatus, "./saveData/hd2_snapshot.json")
            print(self.apistatus.war)
            hd2.add_to_csv(self.apistatus)
        return

    async def make_planets(self, ctx, usebiome=""):
        print("Updating planets.")
        async def update_planet(planet, ctx):
            planetbiome = self.apistatus.planetdata["planets"].get(
                str(planet.index), None
            )

            if planetbiome:
                print(planetbiome["biome"])
                if usebiome:
                    if planetbiome["biome"] != usebiome:
                        return
                thread = asyncio.to_thread(
                    hd2.get_planet, planet.index, planetbiome["biome"]
                )
                await thread

        ttasks = []
        for _, planet in self.apistatus.planets.items():
            planetbiome = self.apistatus.planetdata["planets"].get(
                str(planet.index), None
            )

            if planetbiome:
                print(planetbiome["biome"])
                if usebiome:
                    if planetbiome["biome"] != usebiome:
                        continue
                ttasks.append(update_planet(planet, ctx))
        lst = [ttasks[i : i + 8] for i in range(0, len(ttasks), 8)]
        allv = len(lst)
        for e, ttas in enumerate(lst):
            await asyncio.gather(*ttas)

            await ctx.send(f"Done with chunk {e+1}:{allv}.")

    def draw_img(self):
        """Create a GIF map."""
        print("Updating map.")
        file_path = "./assets/GalacticMap.png"
        img = hd2.create_gif(file_path, apistat=self.apistatus)
        self.img = img

    async def update_api(self):

        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )
        try:
            print("updating war")
            await self.update_data()

            await asyncio.gather(asyncio.to_thread(self.draw_img), asyncio.sleep(1))

        except Exception as e:
            await self.bot.send_error(e, f"Message update cleanup error.")
            gui.gprint(str(e))

    async def gtask_update(self, source_message: discord.Message = None):
        """
        Guild task that updates the overview message.
        """
        if not source_message:
            return None
        context = await self.bot.get_context(source_message)
        try:
            profile = ServerHDProfile.get(context.guild.id)
            if profile:

                target = await urltomessage(profile.overview_message_url, context.bot)
                if self.api_up is False:
                    await target.edit(content="**WARNING, COMMS ARE DOWN!**")
                    return
                emb = hd2.campaign_view(self.apistatus, self.hd2)

                embs = [emb]
                if self.apistatus.assignments:
                    for i, assignment in self.apistatus.assignments.items():
                        b, a = assignment.get_first_change()
                        embs.insert(
                            0,
                            hd2.create_assignment_embed(
                                b, b - a, planets=self.apistatus.planets
                            ),
                        )

                await target.edit(content="Current game status.", embeds=embs)
                return "OK"
        except Exception as e:
            er = MessageTemplates.get_error_embed(
                title=f"Error with AUTO", description=f"{str(e)}"
            )
            await source_message.channel.send(embed=er)
            raise e

    async def gtask_map(self, source_message: discord.Message = None):
        """
        Guild task that updates the overview message.
        """
        if not source_message:
            return "REMOVE"
        context = await self.bot.get_context(source_message)
        try:
            profile = ServerHDProfile.get(context.guild.id)
            if profile:

                await self.get_map(context)
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
    @commands.command(name="make_planets")
    async def planetmaker(self, ctx: commands.Context, usebiome: str = ""):

        await ctx.send("Making planets")
        await self.make_planets(ctx, usebiome)

        await ctx.send("made planets")

    @commands.is_owner()
    @commands.command(name="get_csv")
    async def get_csv(self, ctx: commands.Context):
        hd2.write_statistics_to_csv(self.apistatus)
        await ctx.send(file=discord.File("statistics.csv"))
        await ctx.send(file=discord.File("statistics_sub.csv"))

        await ctx.send(file=discord.File("statistics_new.csv"))

    @commands.is_owner()
    @commands.command(name="get_map")
    async def mapget(self, context: commands.Context):
        await self.get_map(context)

    async def get_map(self, context: commands.Context):
        img = self.img
        globtex = ""
        if self.apistatus.warall:
            for evt in self.apistatus.warall.status.globalEvents:
                if evt.title and evt.message:
                    mes = re.sub(hd2.pattern, r"**\1**", evt.message)
                    mes = re.sub(hd2.pattern3, r"***\1***", mes)
                    globtex += f"### {evt.title}\n{mes}\n\n"

        profile = ServerHDProfile.get_or_new(context.guild.id)
        if profile.last_global_briefing != globtex:
            profile.update(last_global_briefing=globtex)
        else:
            globtex = ""
        war = self.apistatus.war.get_first()
        stats = war.statistics.format_statistics()
        embed = discord.Embed(
            title="Daily Galactic War Status.",
            description=f"{globtex}\n"[:4096],
            color=0x0000FF,
        )
        if not img:
            await asyncio.gather(asyncio.to_thread(self.draw_img), asyncio.sleep(1))
            img = self.img

        print(img)
        liberations, defenses = 0, 0
        for i, campl in self.apistatus.campaigns.items():
            this = campl.get_first()
            if this.planet.event:
                defenses += 1
            else:
                liberations += 1
        embed.add_field(name="War Stats", value=f"{stats[:1000]}", inline=False)
        embed.add_field(
            name="Current Field",
            value=f"Liberations:{liberations}\n Defences:{defenses}",
        )
        embed.set_image(url="attachment://map.gif")
        embed.timestamp = discord.utils.utcnow()
        await context.send(embed=embed, file=discord.File(img))

    @commands.is_owner()
    @commands.command(name="api_down")
    async def api_off(self, ctx: commands.Context):
        self.api_up = not self.api_up
        await ctx.send(f"Api set is {self.api_up}")

    pcs = app_commands.Group(
        name="hd2setup",
        description="Commands for Helldivers 2 setup.",
        guild_only=True,
        default_permissions=discord.Permissions(
            manage_messages=True, manage_channels=True
        ),
    )

    @pcs.command(
        name="make_overview", description="Setup a constantly updating message "
    )
    async def overview_make(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        profile = ServerHDProfile.get_or_new(ctx.guild.id)
        guild = ctx.guild
        task_name = "UPDATEOVERVIEW"
        autochannel = ctx.channel

        target_message = await autochannel.send(
            "Overview_message", view=HD2OverviewView(self)
        )
        old = TCGuildTask.get(guild.id, task_name)
        url = target_message.jump_url
        profile.update(overview_message_url=url)
        if not old:
            now = datetime.now()
            start_date = datetime(2023, 1, 1, now.hour, 2)
            robj = rrule(freq=MINUTELY, interval=15, dtstart=start_date)

            new = TCGuildTask.add_guild_task(
                guild.id, task_name, target_message, robj, True
            )
            new.to_task(ctx.bot)

            result = f"Overview message set.  every 15 minutes, this message will update with the latest galactic status.  Please don't delete it unless you want to stop."
            await ctx.send(result)
        else:
            old.target_channel_id = autochannel.id
            now = datetime.now()
            start_date = datetime(2023, 1, 1, now.hour, 2)
            robj = rrule(freq=MINUTELY, interval=15, dtstart=start_date)
            # target_message = await autochannel.send("**ALTERING AUTO CHANNEL...**",view=HD2OverviewView(self))
            old.target_message_url = target_message.jump_url
            old.change_rrule(ctx.bot, robj)
            self.bot.database.commit()
            result = f"Changed the dashboard channel to <#{autochannel.id}>"
            await ctx.send(result)

    @pcs.command(
        name="subscribe_for_maps", description="Subscribe for daily war map gifs."
    )
    async def map_subscribe(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        profile = ServerHDProfile.get_or_new(ctx.guild.id)
        guild = ctx.guild
        task_name = "WARSTATUS"
        autochannel = ctx.channel

        target_message = await autochannel.send(
            "MESSAGE FOR REOCCURING GALACTIC STATUS, DELETE IF YOU WANT TO STOP."
        )
        old = TCGuildTask.get(guild.id, task_name)
        url = target_message.jump_url
        if not old:
            now = datetime.now()
            start_date = datetime(2023, 1, 1, 20, 5)
            robj = rrule(freq=DAILY, interval=1, dtstart=start_date)

            new = TCGuildTask.add_guild_task(
                guild.id, task_name, target_message, robj, True
            )
            new.to_task(ctx.bot)

            result = f"Overview message set.  every DAY, this message will update with the latest galactic status.  Please don't delete it unless you want to stop."
            await ctx.send(result)
        else:
            old.target_channel_id = autochannel.id

            # target_message = await autochannel.send("**ALTERING AUTO CHANNEL...**",view=HD2OverviewView(self))
            old.target_message_url = target_message.jump_url
            self.bot.database.commit()
            result = f"Changed the regular update channel to <#{autochannel.id}>"
            await ctx.send(result)

    pc = app_commands.Group(name="hd2", description="Commands for Helldivers 2.")

    @pc.command(name="war", description="get war state.")
    async def warstat(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus.war:
            return await ctx.send("No result")
        this, last = self.apistatus.war.get_first_change()
        await ctx.send(embed=hd2.create_war_embed(self.apistatus))
        return

    @pc.command(name="assign", description="get assignment state.")
    async def assignstate(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus.assignments:
            return await ctx.send("No result")

        for ind, key in self.apistatus.assignments.items():
            this, last = key.get_first_change()
            await ctx.send(
                embed=hd2.create_assignment_embed(
                    this, this - last, planets=self.apistatus.planets
                )
            )

    @commands.is_owner()
    @commands.command(name="assigntest")
    async def assigntest(self, context: commands.Context):
        for ind, key in self.apistatus.assignments.items():
            this, last = key.get_first_change()
            img = this.get_overview_image(self.apistatus.planets)
            with io.BytesIO() as image_binary:
                img.save(image_binary, "PNG")
                image_binary.seek(0)
                await context.send(
                    embed=hd2.create_assignment_embed(
                        this, this - last, planets=self.apistatus.planets
                    ),
                    file=discord.File(fp=image_binary, filename="overview.png"),
                )

    async def planet_autocomplete(self, interaction: discord.Interaction, current: str):
        """
        Autocomplete for planet lookup.  Search by either the name or index.
        """
        planets = self._shared_autocomplete_logic(
            self.apistatus.planets.values(), current
        )
        print(planets)
        return planets

    async def campaign_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """
        Autocomplete for planet lookup.  Search by either the name or index.
        """
        campaigns = (l.get_first().planet for l in self.apistatus.campaigns.values())
        planets = self._shared_autocomplete_logic(campaigns, current)
        print(planets)
        return planets

    def _shared_autocomplete_logic(self, items, current: str):
        """Shared autocomplete logic."""
        search_val = current.lower()
        results = []
        for v in items:
            if len(results) >= 25:
                break
            if search_val in v.get_name(False).lower():
                results.append(
                    app_commands.Choice(name=v.get_name(False), value=int(v.index))
                )
        return results

    @pc.command(name="campaigns", description="get campaign state.")
    @app_commands.choices(
        filter=[  # param name
            Choice(name="View campaigns for all planets", value=0),
            Choice(name="View campaigns for bug planets only", value=2),
            Choice(name="View campaigns for bot planets", value=3),
        ]
    )
    @app_commands.autocomplete(byplanet=campaign_autocomplete)
    @app_commands.describe(byplanet="view campaign for this specific planet index.")
    async def cstate(
        self,
        interaction: discord.Interaction,
        filter: Literal[0, 2, 3] = 0,
        byplanet: int = 0,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus.campaigns:
            return await ctx.send("No result")
        embeds = []

        for ind, key in self.apistatus.campaigns.items():
            camp, last = key.get_first_change()
            diff = camp.planet - last.planet
            if byplanet != 0:
                if camp.planet.index == byplanet:

                    embeds.append(
                        hd2.create_planet_embed(
                            camp.planet, cstr=camp, last=diff, stat=self.apistatus
                        )
                    )
            else:
                if filter == 0:
                    embeds.append(
                        hd2.create_planet_embed(
                            camp.planet, cstr=camp, last=diff, stat=self.apistatus
                        )
                    )
                elif filter == 2:
                    evtcheck = camp["planet"]["event"]
                    if evtcheck:
                        evtcheck = evtcheck["faction"] == "Terminids"
                    if camp["planet"]["currentOwner"] == "Terminids" or evtcheck:
                        embeds.append(
                            hd2.create_planet_embed(
                                camp.planet, cstr=camp, last=diff, stat=self.apistatus
                            )
                        )
                elif filter == 3:
                    evtcheck = camp["planet"]["event"]
                    if evtcheck:
                        evtcheck = evtcheck["faction"] == "Automaton"
                    if camp["planet"]["currentOwner"] == "Automaton" or evtcheck:
                        embeds.append(
                            hd2.create_planet_embed(
                                camp.planet, cstr=camp, last=diff, stat=self.apistatus
                            )
                        )
        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)

    @pc.command(name="planet", description="get data for a single specific planet")
    @app_commands.autocomplete(byplanet=planet_autocomplete)
    @app_commands.describe(byplanet="view specific planet index.")
    async def pstate(self, interaction: discord.Interaction, byplanet: int):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.planets
        if not data:
            return await ctx.send("No result")
        embeds = []
        print(byplanet)
        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            embeds.append(
                hd2.create_planet_embed(
                    planet, cstr=None, last=None, stat=self.apistatus
                )
            )
            await ctx.send(embeds=embeds, ephemeral=True)
            # await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)
        else:
            await ctx.send("Planet not found.", ephemeral=True)

    @pc.command(name="dispatches", description="get a list of all dispatches.")
    async def dispatch(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.dispatches
        if not data:
            return await ctx.send("No result")
        embeds = []
        for s in data:
            embeds.append(s.to_embed())
        await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)

    @pc.command(
        name="overview", description="Return the current state of the HD2 Galactic War."
    )
    async def campoverview(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.campaigns

        if not data:
            return await ctx.send("No result")
        emb = hd2.campaign_view(self.apistatus, self.hd2)
        await ctx.send(embed=emb)

    @pc.command(name="map", description="get a primitive galactic map.")
    @app_commands.describe(planet="Focus map on this planet.")
    @app_commands.autocomplete(planet=planet_autocomplete)
    async def map(self, interaction: discord.Interaction, planet: int = 0):
        ctx: commands.Context = await self.bot.get_context(interaction)
        mes = await ctx.send("please wait...", ephemeral=True)
        img = self.img
        if not img:
            await asyncio.gather(asyncio.to_thread(self.draw_img), asyncio.sleep(1))
            img = self.img
            # await mes.edit(content="Image not available.")
            # return
        cx, cy = 0, 0
        if planet in self.apistatus.planets:
            pos = self.apistatus.planets[planet].position
            cx, cy = pos.x, pos.y
        view = hd2.MapViewer(
            user=ctx.author, img=img, initial_coor=hd2.get_im_coordinates(cx, cy)
        )
        emb, file = view.make_embed()
        await mes.edit(content="done", attachments=[file], embed=emb, view=view)


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
