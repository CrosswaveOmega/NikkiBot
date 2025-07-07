import asyncio
import io
import logging
import gui
from typing import Literal
from assetloader import AssetLookup
import discord
import random
from datetime import datetime, timedelta
from discord import app_commands
import importlib

from dateutil.rrule import MINUTELY, DAILY, rrule
from discord.ext import commands

from discord.app_commands import Choice

from utility import MessageTemplates, urltomessage
from bot import (
    Guild_Task_Functions,
    TC_Cog_Mixin,
    TCBot,
    TCGuildTask,
)

# import datetime
from .HD2.db import ServerHDProfile
import cogs.HD2 as hd2
import hd2api
from utility.embed_paginator import pages_of_embeds, pages_of_embeds_2
from utility import load_json_with_substitutions
from utility import WebhookMessageWrapper as web
from bot.Tasks import TCTask, TCTaskManager

from hd2api.builders import get_time_dh

from hd2api import hdml_parse
from discord.utils import format_dt as fdt


class HD2OverviewView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.my_count = {}
        self.cog: "HelldiversCog" = cog

    async def callback(self, interaction, button):
        user = interaction.user
        label = button.label
        if str(user.id) not in self.my_count:
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
            "Embed",
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
        try:
            await self.est(interaction, button)
        except Exception as e:
            await self.cog.bot.send_error(e, "view_error")

    async def est(self, interaction: discord.Interaction, button: discord.ui.Button):
        est = self.cog.apistatus.estimates()
        gui.gprint(est)
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
        if len(embeds) > 1:
            pcc, _ = await pages_of_embeds_2(True, embeds, show_page_nums=False)
            but = hd2.ListButtons(callbacker=pcc)
            await interaction.response.send_message(
                embed=pcc.make_embed(), view=but, ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)

    @discord.ui.button(
        label="Space Stations",
        style=discord.ButtonStyle.blurple,
        custom_id="hd_persistent_view:station_blue",
    )
    async def show_stations(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        stations = await self.cog.apistatus.get_station()
        gui.gprint(stations)
        embeds = []
        for name, val in stations.items():
            emb = hd2.station_embed(
                self.cog.apistatus,
                val,
            )
            embeds.append(emb)
        if not embeds:
            embeds.append(discord.Embed(title="NO STATION DATA."))
        if len(embeds) > 1:
            pcc, _ = await pages_of_embeds_2(True, embeds, show_page_nums=False)
            but = hd2.ListButtons(callbacker=pcc)
            await interaction.response.send_message(
                embed=pcc.make_embed(), view=but, ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)

    @discord.ui.button(
        label="View App",
        style=discord.ButtonStyle.grey,
        emoji="<:divericon:1270027381154910322>",
        custom_id="hd_persistent_view:grey",
    )
    async def map(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "https://helldiverscompanion.com/",
            ephemeral=True,
        )
        # await self.callback(interaction, button)


class HelldiversCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        self.get_running = False
        # self.session=aiohttp.ClientSession()
        hdoverride = hd2api.APIConfig(
            static_path="./hd2json", use_raw="direct", timeout=15
        )
        hd2api.set_fdt(discord.utils.format_dt)
        hd2api.setuphd2logging("./logs/")
        self.img = None
        hdoverride.client_name = bot.keys.get("hd2cli")
        self.apistatus = hd2.ApiStatus(client=hdoverride)

        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )
        self.api_up = True
        self.outstring = ""
        snap = hd2.load_from_json("./saveData/hd2_snapshot.json")
        if snap:
            try:
                if "nowall" in snap:
                    snap.pop("nowall")
                new_cls = hd2.ApiStatus.from_dict(snap, client=hdoverride)
                self.apistatus = new_cls
            except Exception as e:
                gui.gprint(e)
                self.bot.logs.exception(e)
                log = logging.getLogger("discord")
                log.error("An error has been raised: %s", e, exc_info=e)
        Guild_Task_Functions.add_task_function("UPDATEOVERVIEW", self.gtask_update)
        Guild_Task_Functions.add_task_function("WARSTATUS", self.gtask_map)

        self.bot.add_view(HD2OverviewView(self))
        this_planet = self.apistatus.planets.get(64, None)
        if not this_planet:
            gui.gprint("NOPLANET")
        else:
            this = this_planet.position
            if not this:
                self.last = hd2api.Position(0, 0)
            else:
                self.last = this
        self.last_speed = None
        self.speeds = hd2.GameStatus.LimitedSizeList(8)

        nowd = datetime.now()
        self.loghook = AssetLookup.get_asset("loghook", "urls")
        st = datetime(
            nowd.year, nowd.month, nowd.day, nowd.hour, int(nowd.minute / 5) * 5
        )
        robj = rrule(freq=MINUTELY, interval=5, dtstart=st)
        if not TCTaskManager.does_task_exist("SuperEarthStatus"):
            self.tc_task = TCTask("SuperEarthStatus", robj, robj.after(st))
            self.tc_task.assign_wrapper(self.update_api)

        start_date = datetime(2023, 1, 1, 19, 48)
        robj = rrule(freq=DAILY, interval=1, dtstart=start_date)
        if not TCTaskManager.does_task_exist("SuperEarthMapMaker"):
            self.tc_task = TCTask("SuperEarthMapMaker", robj, robj.after(st))
            self.tc_task.assign_wrapper(self.make_map)
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
        # hd2.save_to_json(self.apistatus, "./saveData/hd2_snapshot.json")
        TCTaskManager.remove_task("SuperEarthStatus")
        Guild_Task_Functions.remove_task_function("WARSTATUS")
        Guild_Task_Functions.remove_task_function("UPDATEOVERVIEW")

    async def planet_tracker(self):
        gui.gprint(self.apistatus.planets.keys())
        this_planet = self.apistatus.planets.get(64, None)
        if not this_planet:
            gui.gprint("No planet")
            self.outstring = "No planet"
            return
        this = this_planet.position
        if not this:
            self.outstring = "NO POSITION FOR MERIDIA"

            return "NO POSITION FOR MERIDIA"

        last = self.last

        difference = this - last

        self.last = this
        self.speeds.add(difference)

        speed = difference.speed()
        current_angle = difference.angle()
        lastspeed = self.last_speed
        if (
            self.last_speed is not None
            and abs(difference.time_delta.total_seconds()) > 0
        ):
            acceleration = (
                speed - self.last_speed
            ) / difference.time_delta.total_seconds()  # Acceleration in units/sec²
        else:
            acceleration = 0.0  # First measurement, no acceleration
        self.last_speed = speed

        speed_avg = hd2api.Position.average(self.speeds.items)

        speed_changes = self.speeds.get_changes()
        accel_avg = 0.0
        if speed_changes:
            accel_avg = hd2api.Position.average(speed_changes).speed()

        target_planet = self.apistatus.planets.get(127, None)
        if not target_planet:
            self.outstring = "NO TARGET PLANET FOR MERIDIA"
            return
        target = target_planet.position
        target_diff = target - this
        target_mag = target_diff.mag()
        target_angle = target_diff.angle()

        time_to_target = this.estimate_time_to_target(target, speed, acceleration)
        speed_only_time = this.estimate_time_to_target(target, speed, 0.0)

        time_to_target_avg = this.estimate_time_to_target(
            target, speed_avg.speed(), accel_avg
        )
        avg_speed_only_time = this.estimate_time_to_target(
            target, speed_avg.speed(), 0.0
        )

        outstring = (
            f"Previous Meridia Position: ({last.x},{last.y})\n"
            f"New Meridia Position: ({this.x},{this.y})\n"
            f"Position Delta: ({difference.x:.10f},{difference.y:.10f})\n"
            f"Duration for Difference: {difference.time_delta}\n"
            f"Speed: {speed:.10f} units/sec\n"
            f"LastSpeed: {lastspeed:.10f} units/sec\n"
            f"Acceleration: {acceleration:.10f} units/sec²\n"
            f"AverageSpeed: {speed_avg.speed():.10f} units/sec from {len(self.speeds.items)} entries\n"
            f"Average Time Delta: {speed_avg.time_delta} \n"
            f"AverageAcceleration: {accel_avg:.10f} units/sec² from {len(speed_changes)} differences \n"
            f"Current Trajectory: {current_angle:.2f}° (Clockwise from +Y-axis)\n"
            f"Distance to target is {target_mag} units.\n"
            f"Required Trajectory to Reach Target: {target_angle:.2f}° (Clockwise)\n"
            f"Estimated time to reach target: {time_to_target}\n"
            f"Estimated time to reach target average: {time_to_target_avg}\n"
            f"Estimated time to reach target without accel: {speed_only_time}\n"
            f"Estimated time to reach target average without accel: {avg_speed_only_time}\n"
        )
        self.outstring = outstring
        gui.gprint(outstring)

    async def update_data(self):
        if self.api_up:
            await self.apistatus.update_data()
            hd2.save_to_json(self.apistatus.to_dict(), "./saveData/hd2_snapshot.json")
            # gui.gprint(self.apistatus.war)
            hd2.add_to_csv(self.apistatus)

            # await self.planet_tracker()
        return

    async def make_planets(self, ctx, usebiome=""):
        gui.gprint("Updating planets.")

        async def update_planet(planet, ctx):
            planetbiome = self.apistatus.statics.galaxystatic["planets"].get(
                planet.index, None
            )
            if planetbiome:
                if usebiome:
                    if planetbiome["biome"] != usebiome:
                        return
                thread = asyncio.to_thread(
                    hd2.get_planet, planet.index, planetbiome["biome"]
                )
                await thread

        ttasks = []
        for _, planet in self.apistatus.planets.items():
            planetbiome = self.apistatus.statics.galaxystatic["planets"].get(
                planet.index, None
            )

            if planetbiome:
                if usebiome:
                    if planetbiome["biome"] != usebiome:
                        continue
                ttasks.append(update_planet(planet, ctx))
        lst = [ttasks[i : i + 8] for i in range(0, len(ttasks), 8)]
        allv = len(lst)
        for e, ttas in enumerate(lst):
            await asyncio.gather(*ttas)

            await ctx.send(f"Done with chunk {e + 1}:{allv}.")

    async def make_map(self):
        """Create a GIF map."""

        gui.gprint("updating map")
        try:
            await asyncio.gather(asyncio.to_thread(self.draw_img), asyncio.sleep(1))
            gui.gprint("Updating map.")
            file_path = "./assets/GalacticMap.png"
            img = hd2.create_png(file_path, apistat=self.apistatus)
            self.img = img
        except Exception as e:
            await self.bot.send_error(e, "Message update cleanup error.")
            # gui.gprint(str(e))

    def draw_img(self):
        """Create a GIF map."""
        gui.gprint("Updating map.")
        file_path = "./assets/GalacticMap.png"
        img = hd2.create_png(file_path, apistat=self.apistatus)
        self.img = img

    async def update_api(self):
        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )
        try:
            gui.gprint("updating war")
            await self.update_data()
            # await asyncio.gather(asyncio.to_thread(self.draw_img), asyncio.sleep(1))

        except Exception as e:
            await self.bot.send_error(e, "Message update cleanup error.")
            # gui.gprint(str(e))
            
    async def edit_target_message(self, context, stalemated=True):
        profile = ServerHDProfile.get(context.guild.id)
        if profile:
            target = await urltomessage(profile.overview_message_url, context.bot)
            if self.api_up is False:
                await target.edit(content="**WARNING, COMMS ARE DOWN!**")
                return
            emb = hd2.campaign_view(self.apistatus, self.hd2,show_stalemated=stalemated)
            embs = emb
            if self.apistatus.assignments:
                for i, assignment in self.apistatus.assignments.items():
                        b, a = assignment.get_first_change()
                        emb3 = hd2.create_assignment_embed(
                            b, b - a, planets=self.apistatus.planets
                        )

                        embs.insert(
                            0,
                            emb3,
                        )
            output_string = self.outstring
            if output_string:
                    embs.insert(
                        0,
                        discord.Embed(
                            title="Meridia Status.",
                            description=f"{output_string}"[:4090],
                        ),
                    )

            await target.edit(content="Current game status.", embeds=embs)
            
    async def gtask_update(self, source_message: discord.Message = None):
        """
        Guild task that updates the overview message.
        """
        if not source_message:
            return None
        context = await self.bot.get_context(source_message)
        try:
            await self.edit_target_message(context,stalemated=True)
            return "OK"
        except Exception as e:
            try:
                await self.edit_target_message(context,stalemated=False)
                return "OK"
            except Exception as e:
                er = MessageTemplates.get_error_embed(
                    title="Error with AUTO", description=f"{str(e)}"
                )
            
                await source_message.channel.send(embed=er)
                raise e

    async def gtask_map(self, source_message: discord.Message = None):
        """
        Guild task that creates a map.
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
                title="Error with AUTO", description=f"{str(e)}"
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
        await ctx.send(file=discord.File("statistics_newer.csv"))

    @commands.is_owner()
    @commands.command(name="direct_mode")
    async def direct_mode(self, ctx: commands.Context):
        self.apistatus.direct = not self.apistatus.direct
        await ctx.send(f"Direct mode set to {self.apistatus.direct}")

    @commands.is_owner()
    @commands.command(name="get_map")
    async def mapget(self, context: commands.Context):
        await self.get_map(context)

    @commands.is_owner()
    @commands.command(name="get_avg")
    async def meridiaget(self, context: commands.Context):
        if not self.outstring:
            await self.planet_tracker()
        await context.send(self.outstring)

    async def get_map(self, context: commands.Context):
        img = self.img
        globtex = ""
        if self.apistatus.warall:
            for evt in self.apistatus.warall.status.globalEvents:
                if evt.title and evt.message:
                    mes = hd2api.hdml_parse(evt.message)
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

        # gui.gprint(img)
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
        embed.set_image(url="attachment://map.png")
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

    @commands.is_owner()
    @commands.command(name="correct_overview")
    async def correctover(
        self, context: commands.Context, guildid: int, channelid: int, edit: bool = True
    ):
        guild = context.bot.get_guild(guildid)
        channel = context.bot.get_channel(channelid)
        await self.overview_make_logic(context, guild, channel, edit=edit)

    async def overview_make_logic(self, ctx, guild, autochannel, edit=False):
        """This function makes a dashboard message for the bot."""
        target_message = None
        profile = ServerHDProfile.get_or_new(guild.id)
        if profile.overview_message_url:
            target_message = await urltomessage(profile.overview_message_url, ctx.bot)
            if target_message and not edit:
                await target_message.delete()
                target_message = None

        task_name = "UPDATEOVERVIEW"
        if not target_message:
            target_message = await autochannel.send(
                "Overview_message", view=HD2OverviewView(self)
            )
            url = target_message.jump_url
            profile.update(overview_message_url=url)
        elif target_message and edit == True:
            await target_message.edit(view=HD2OverviewView(self))

        old = TCGuildTask.get(guild.id, task_name)

        if not old:
            now = datetime.now()
            start_date = datetime(2023, 1, 1, now.hour, 2)
            robj = rrule(freq=MINUTELY, interval=15, dtstart=start_date)

            new = TCGuildTask.add_guild_task(
                guild.id, task_name, target_message, robj, True
            )
            new.to_task(ctx.bot)

            result = "Overview message set.  every 15 minutes, this message will update with the latest galactic status.  Please don't delete it unless you want to stop."
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
        name="stop_overview",
        description="stop the galactic war overview dashboard in this server. ",
    )
    async def overview_stop(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        target_message = None
        guild = ctx.guild
        profile = ServerHDProfile.get_or_new(guild.id)
        if profile.overview_message_url:
            target_message = await urltomessage(profile.overview_message_url, ctx.bot)
            if target_message:
                await target_message.delete()
                target_message = None

        task_name = "UPDATEOVERVIEW"
        old = TCGuildTask.get(guild.id, task_name)

        if not old:
            result = "There's no dashboard"
            await ctx.send(result)
        else:
            TCGuildTask.remove_guild_task(guild.id, task_name)

            self.bot.database.commit()
            result = "Dashboard cancelled."
            await ctx.send(result)

    @pcs.command(
        name="make_overview", description="Setup a constantly updating message "
    )
    async def overview_make(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        await self.overview_make_logic(ctx, ctx.guild, ctx.channel, False)

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

            result = "Overview message set.  every DAY, this message will update with the latest galactic status.  Please don't delete it unless you want to stop."
            await ctx.send(result)
        else:
            old.target_channel_id = autochannel.id

            # target_message = await autochannel.send("**ALTERING AUTO CHANNEL...**",view=HD2OverviewView(self))
            old.target_message_url = target_message.jump_url
            self.bot.database.commit()
            result = f"Changed the regular update channel to <#{autochannel.id}>"
            await ctx.send(result)

    @pcs.command(
        name="unsubscribe_for_maps", description="Unsubscribe from daily war map gifs."
    )
    async def map_unsubscribe(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        profile = ServerHDProfile.get_or_new(ctx.guild.id)
        guild = ctx.guild
        task_name = "WARSTATUS"
        old = TCGuildTask.get(guild.id, task_name)
        if not old:
            result = (
                "It doesn't look like you're subscribed to the daily galactic war maps."
            )
            await ctx.send(result)
        else:
            TCGuildTask.remove_guild_task(ctx.guild.id, task_name)

            self.bot.database.commit()
            result = "Unsubscribed to daily galactic war maps."
            await ctx.send(result)

    @pcs.command(
        name="real_time_log_subscribe", description="Subscribe to the real time log."
    )
    @app_commands.describe(channel="Channel to add the real time log webhook to")
    async def real_time_log_subscribe(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)

        profile = ServerHDProfile.get_or_new(ctx.guild.id)
        guild = ctx.guild
        # task_name = "WARSTATUS"
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.manage_webhooks:
            await ctx.send("Cannot make webhook in this channel", ephemeral=True)
            return
        webhook, thread = await web.getWebhookInChannel(channel)
        profile.update(webhook_url=webhook.url)
        await ctx.send(
            f"Real Time log webhook subscription created with webhook {webhook.url}",
            ephemeral=True,
        )
        hooks = ServerHDProfile.get_entries_with_webhook()
        # await ctx.send(f"{hooks}", ephemeral=True)
        lg = [AssetLookup.get_asset("loghook", "urls")]
        for h in hooks:
            lg.append(h)
        self.bot.get_cog("HelldiversAutoLog").loghook = lg

    @pcs.command(
        name="real_time_log_unsubscribe",
        description="Unsubscribe to the real time log.",
    )
    @app_commands.describe()
    async def real_time_log_unsubscribe(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        profile = ServerHDProfile.get_or_new(ctx.guild.id)
        guild = ctx.guild
        # task_name = "WARSTATUS"

        profile.update(webhook_url=None)
        await ctx.send("Real Time log webhook subscription cancelled.", ephemeral=True)
        hooks = ServerHDProfile.get_entries_with_webhook()
        lg = [AssetLookup.get_asset("loghook", "urls")]
        for h in hooks:
            lg.append(h)
        self.bot.get_cog("HelldiversAutoLog").loghook = lg

    pc = app_commands.Group(name="hd2", description="Commands for Helldivers 2.")

    @pc.command(name="help", description="Learn how to use the helldivers commands")
    async def getmanual(self, interaction: discord.Interaction) -> None:
        """Return a manual about the Helldivers features"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        pages = await MessageTemplates.get_manual_list(
            ctx, "nikki_helldivers_manual.json"
        )
        await pages_of_embeds(ctx, pages, ephemeral=True)

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

    @pc.command(name="station", description="get space station embed.")
    async def stationstate(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        gui.gprint("GETTING STATIONS")
        stations = await self.apistatus.get_station()
        for i, v in stations.items():
            await ctx.send(
                embed=hd2.station_embed(
                    self.apistatus,
                    v,
                ),
                ephemeral=True,
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
        # gui.gprint(planets)
        return planets

    async def campaign_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """
        Autocomplete for planet lookup.  Search by either the name or index.
        """
        campaigns = (l.get_first().planet for l in self.apistatus.campaigns.values())
        planets = self._shared_autocomplete_logic(campaigns, current)
        # gui.gprint(planets)
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

    @pc.command(
        name="planetregions", description="View region data for a specific planet"
    )
    @app_commands.autocomplete(byplanet=planet_autocomplete)
    @app_commands.describe(byplanet="View regions for a specific planet index.")
    async def pregion(self, interaction: discord.Interaction, byplanet: int):
        ctx: commands.Context = await self.bot.get_context(interaction)

        if not self.apistatus or not self.apistatus.regions:
            return await ctx.send("No region data is available.", ephemeral=True)

        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            # Check if any regions exist for the given planet index

            # Generate the embed(s)
            embeds = hd2.region_view(
                stat=self.apistatus,
                planet=planet,
                hdtext=self.hd2,  # Optional: use if you're managing flavor text
                full=False,
                show_stalemate=True,
            )

            await ctx.send(embeds=embeds, ephemeral=True)

    @commands.command()
    @commands.is_owner()
    async def illuminate_test(self, ctx: commands.Context):
        data = self.apistatus.planets
        if not data:
            return await ctx.send("No result")

        planets = random.sample(list(self.apistatus.planets.values()), 25)
        campaigns = []
        for c in self.apistatus.campaigns.values():
            campaigns.append(c.get_first())
        for planet in planets:
            planet.currentOwner = "Illuminate"
            campaigns.append(
                hd2api.models.Campaign2(
                    id=random.randint(10000000, 999999999),
                    planet=planet,
                    type=3,
                    count=29,
                )
            )

        self.apistatus.handle_data(campaigns, self.apistatus.campaigns, "assignment")

        await ctx.send("Spoofed!", ephemeral=True)

    @pc.command(name="dispatches", description="get a list of all dispatches.")
    async def dispatch(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apistatus.warall.news_feed
        if not data:
            return await ctx.send("No result")
        embeds = []
        timestart = get_time_dh(self.apistatus.warall)
        for s in data:
            timev = timestart + (timedelta(seconds=s.published))
            embeds.append(
                discord.Embed(
                    title=f"Dispatch {s.id}, type {s.type}",
                    description=f"{hdml_parse(s.message)}\n{fdt(timev)}",
                )
            )
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
        await ctx.send(embeds=emb)

    # @pc.command(name="map", description="get a scrollable galactic map.")
    # @app_commands.describe(planet="Focus map on this planet.")
    # @app_commands.describe(animated="Show an animated map, take more time to scroll.")
    # @app_commands.autocomplete(planet=planet_autocomplete)
    # async def map(
    #     self, interaction: discord.Interaction, planet: int = 0, animated: bool = False
    # ):
    #     ctx: commands.Context = await self.bot.get_context(interaction)
    #     mes = await ctx.send("please wait...", ephemeral=True)
    #     img = self.img
    #     if not img:
    #         await asyncio.gather(asyncio.to_thread(self.draw_img), asyncio.sleep(1))
    #         img = self.img
    #         # await mes.edit(content="Image not available.")
    #         # return
    #     cx, cy = 0, 0
    #     if planet in self.apistatus.planets:
    #         pos = self.apistatus.planets[planet].position
    #         cx, cy = pos.x, pos.y
    #     view = hd2.MapViewer(
    #         user=ctx.author,
    #         img=img,
    #         initial_coor=hd2.get_im_coordinates(cx, cy),
    #         oneonly=animated,
    #     )
    #     emb, file = view.make_embed()
    #     await mes.edit(content="done", attachments=[file], embed=emb, view=view)

    @app_commands.command(
        name="stratagem_roulette", description="Get a random stratagem loadout."
    )
    async def stratagem_roulette(
        self, interaction: discord.Interaction, rolls: app_commands.Range[int, 1, 9]
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        stratagems = [
            (
                "<:MachineGun:1272565567710036031>",
                "[MG-43 Machine Gun](https://helldivers.wiki.gg/wiki/MG-43_Machine_Gun)",
            ),
            (
                "<:AntiMaterielRifle:1272564847078277161>",
                "[APW-1 Anti-Materiel Rifle](https://helldivers.wiki.gg/wiki/APW-1_Anti-Materiel_Rifle)",
            ),
            (
                "<:Stalwart:1272566085924683786>",
                "[M-105 Stalwart](https://helldivers.wiki.gg/wiki/M-105_Stalwart)",
            ),
            (
                "<:ExpendableAntiTank:1272565302517043210>",
                "[EAT-17 Expendable Anti-Tank](https://helldivers.wiki.gg/wiki/EAT-17_Expendable_Anti-Tank)",
            ),
            (
                "<:RecoillessRifle:1272565933277188126>",
                "[GR-8 Recoilless Rifle](https://helldivers.wiki.gg/wiki/GR-8_Recoilless_Rifle)",
            ),
            (
                "<:Flamethrower:1272565313858437221>",
                "[FLAM-40 Flamethrower](https://helldivers.wiki.gg/wiki/FLAM-40_Flamethrower)",
            ),
            (
                "<:Autocannon:1272564962572767232>",
                "[AC-8 Autocannon](https://helldivers.wiki.gg/wiki/AC-8_Autocannon)",
            ),
            (
                "<:HeavyMachineGun:1272565463108550709>",
                "[MG-206 Heavy Machine Gun](https://helldivers.wiki.gg/wiki/MG-206_Heavy_Machine_Gun)",
            ),
            (
                "<:AirburstRocketLauncher:1272564831819530360>",
                "[RL-77 Airburst Rocket Launcher](https://helldivers.wiki.gg/wiki/RL-77_Airburst_Rocket_Launcher)",
            ),
            (
                "<:Commando:1272565055753293876>",
                "[MLS-4X Commando](https://helldivers.wiki.gg/wiki/MLS-4X_Commando)",
            ),
            (
                "<:Railgun:1272565923462643814>",
                "[RS-422 Railgun](https://helldivers.wiki.gg/wiki/RS-422_Railgun)",
            ),
            (
                "<:Spear:1272566074352861224>",
                "[FAF-14 Spear](https://helldivers.wiki.gg/wiki/FAF-14_Spear)",
            ),
            (
                "<:OrbitalGatlingBarrage:1272565731426570434>",
                "[Orbital Gatling Barrage](https://helldivers.wiki.gg/wiki/Orbital_Gatling_Barrage)",
            ),
            (
                "<:OrbitalAirburstStrike:1272565671879905423>",
                "[Orbital Airburst Strike](https://helldivers.wiki.gg/wiki/Orbital_Airburst_Strike)",
            ),
            (
                "<:Orbital120mmHEBarrage:1272565596499738624>",
                "[Orbital 120mm HE Barrage](https://helldivers.wiki.gg/wiki/Orbital_120mm_HE_Barrage)",
            ),
            (
                "<:Orbital380mmHEBarrage:1272565611498569809>",
                "[Orbital 380mm HE Barrage](https://helldivers.wiki.gg/wiki/Orbital_380mm_HE_Barrage)",
            ),
            (
                "<:OrbitalWalkingBarrage:1272565880747982908>",
                "[Orbital Walking Barrage](https://helldivers.wiki.gg/wiki/Orbital_Walking_Barrage)",
            ),
            (
                "<:OrbitalLaser:1272565771788091453>",
                "[Orbital Laser](https://helldivers.wiki.gg/wiki/Orbital_Laser)",
            ),
            (
                "<:OrbitalRailcannonStrike:1272565831519436801>",
                "[Orbital Railcannon Strike](https://helldivers.wiki.gg/wiki/Orbital_Railcannon_Strike)",
            ),
            (
                "<:EagleStrafingRun:1272565269230911498>",
                "[Eagle Strafing Run](https://helldivers.wiki.gg/wiki/Eagle_Strafing_Run)",
            ),
            (
                "<:EagleAirstrike:1272565196421992448>",
                "[Eagle Airstrike](https://helldivers.wiki.gg/wiki/Eagle_Airstrike)",
            ),
            (
                "<:EagleClusterBomb:1272565210959314956>",
                "[Eagle Cluster Bomb](https://helldivers.wiki.gg/wiki/Eagle_Cluster_Bomb)",
            ),
            (
                "<:EagleNapalmAirstrike:1272565232673361920>",
                "[Eagle Napalm Airstrike](https://helldivers.wiki.gg/wiki/Eagle_Napalm_Airstrike)",
            ),
            (
                "<:JumpPack:1272565538757021726>",
                "[LIFT-850 Jump Pack](https://helldivers.wiki.gg/wiki/LIFT-850_Jump_Pack)",
            ),
            (
                "<:EagleSmokeStrike:1272565252415819837>",
                "[Eagle Smoke Strike](https://helldivers.wiki.gg/wiki/Eagle_Smoke_Strike)",
            ),
            (
                "<:Eagle110mmRocketPods:1272565087495786620>",
                "[Eagle 110mm Rocket Pods](https://helldivers.wiki.gg/wiki/Eagle_110mm_Rocket_Pods)",
            ),
            (
                "<:Eagle500kgBomb:1272565103384068206>",
                "[Eagle 500kg Bomb](https://helldivers.wiki.gg/wiki/Eagle_500kg_Bomb)",
            ),
            (
                "<:OrbitalPrecisionStrike:1272565792424071250>",
                "[Orbital Precision Strike](https://helldivers.wiki.gg/wiki/Orbital_Precision_Strike)",
            ),
            (
                "<:OrbitalGasStrike:1272565716826062980>",
                "[Orbital Gas Strike](https://helldivers.wiki.gg/wiki/Orbital_Gas_Strike)",
            ),
            (
                "<:OrbitalEMSStrike:1272565701953060968>",
                "[Orbital EMS Strike](https://helldivers.wiki.gg/wiki/Orbital_EMS_Strike)",
            ),
            (
                "<:OrbitalSmokeStrike:1272565865358819378>",
                "[Orbital Smoke Strike](https://helldivers.wiki.gg/wiki/Orbital_Smoke_Strike)",
            ),
            (
                "<:HMGEmplacement:1272565474290438218>",
                "[E/MG-101 HMG Emplacement](https://helldivers.wiki.gg/wiki/E/MG-101_HMG_Emplacement)",
            ),
            (
                "<:ShieldGeneratorRelay:1272566063623573545>",
                "[FX-12 Shield Generator Relay](https://helldivers.wiki.gg/wiki/FX-12_Shield_Generator_Relay)",
            ),
            (
                "<:TeslaTower:1272566110432002149>",
                "[A/ARC-3 Tesla Tower](https://helldivers.wiki.gg/wiki/A/ARC-3_Tesla_Tower)",
            ),
            (
                "<:AntiPersonnelMinefield:1272564857648058369>",
                "[MD-6 Anti-Personnel Minefield](https://helldivers.wiki.gg/wiki/MD-6_Anti-Personnel_Minefield)",
            ),
            (
                "<:SupplyPack:1272566095710257162>",
                "[B-1 Supply Pack](https://helldivers.wiki.gg/wiki/B-1_Supply_Pack)",
            ),
            (
                "<:GrenadeLauncher:1272565339250622575>",
                "[GL-21 Grenade Launcher](https://helldivers.wiki.gg/wiki/GL-21_Grenade_Launcher)",
            ),
            (
                "<:LaserCannon:1272565553306927256>",
                "[LAS-98 Laser Cannon](https://helldivers.wiki.gg/wiki/LAS-98_Laser_Cannon)",
            ),
            (
                "<:IncendiaryMines:1272565486651052032>",
                "[MD-I4 Incendiary Mines](https://helldivers.wiki.gg/wiki/MD-I4_Incendiary_Mines)",
            ),
            (
                "<:GuardDogLaserRover:1272565449183461436>",
                '[AX/LAS-5 "Guard Dog" Rover](https://helldivers.wiki.gg/wiki/AX/LAS-5_%22Guard_Dog%22_Rover)',
            ),
            (
                "<:BallisticShieldBackpack:1272565009855025164>",
                "[SH-20 Ballistic Shield Backpack](https://helldivers.wiki.gg/wiki/SH-20_Ballistic_Shield_Backpack)",
            ),
            (
                "<:ArcThrower:1272564945418190859>",
                "[ARC-3 Arc Thrower](https://helldivers.wiki.gg/wiki/ARC-3_Arc_Thrower)",
            ),
            (
                "<:AntiTankMines:1272564932826632273>",
                "[MD-17 Anti-Tank Mines](https://helldivers.wiki.gg/wiki/MD-17_Anti-Tank_Mines)",
            ),
            (
                "<:QuasarCannon:1272565914537300018>",
                "[LAS-99 Quasar Cannon](https://helldivers.wiki.gg/wiki/LAS-99_Quasar_Cannon)",
            ),
            (
                "<:ShieldGeneratorPack:1272566052341026909>",
                "[SH-32 Shield Generator Pack](https://helldivers.wiki.gg/wiki/SH-32_Shield_Generator_Pack)",
            ),
            (
                "<:MachineGunSentry:1272565584164552776>",
                "[A/MG-43 Machine Gun Sentry](https://helldivers.wiki.gg/wiki/A/MG-43_Machine_Gun_Sentry)",
            ),
            (
                "<:GatlingSentry:1272565324000137311>",
                "[A/G-16 Gatling Sentry](https://helldivers.wiki.gg/wiki/A/G-16_Gatling_Sentry)",
            ),
            (
                "<:MortarSentry:1272565643039735993>",
                "[A/M-12 Mortar Sentry](https://helldivers.wiki.gg/wiki/A/M-12_Mortar_Sentry)",
            ),
            (
                "<:GuardDogBulletRover:1272565434578767934>",
                '[AX/AR-23 "Guard Dog"](https://helldivers.wiki.gg/wiki/AX/AR-23_%22Guard_Dog%22)',
            ),
            (
                "<:AutocannonSentry:1272564978368380960>",
                "[A/AC-8 Autocannon Sentry](https://helldivers.wiki.gg/wiki/A/AC-8_Autocannon_Sentry)",
            ),
            (
                "<:RocketSentry:1272565970413551672>",
                "[A/MLS-4X Rocket Sentry](https://helldivers.wiki.gg/wiki/A/MLS-4X_Rocket_Sentry)",
            ),
            (
                "<:EMSMortarSentry:1272565290890170379>",
                "[A/M-23 EMS Mortar Sentry](https://helldivers.wiki.gg/wiki/A/M-23_EMS_Mortar_Sentry)",
            ),
            (
                "<:PatriotExosuit:1272565903724253224>",
                "[EXO-45 Patriot Exosuit](https://helldivers.wiki.gg/wiki/EXO-45_Patriot_Exosuit)",
            ),
            (
                "<:EmancipatorExosuit:1272565280991875238>",
                "[EXO-49 Emancipator Exosuit](https://helldivers.wiki.gg/wiki/EXO-49_Emancipator_Exosuit)",
            ),
        ]
        embed = discord.Embed(
            title=f"Your Random Stratagem Loadout{'s' if rolls > 1 else ''}",
        )
        desc = "# "
        for r in range(0, rolls):
            random_choices = random.sample(stratagems, 4)
            sload = ""
            known = f"R{r + 1}"
            for e, l in random_choices:
                sload += f"{e}{l}\n"
                known += e
            desc += known
            if ((r + 1) % 3) == 0:
                desc += "\n# "
            else:
                desc += "`   `"
            embed.add_field(name=f"Roll {r + 1}", value=sload)
        embed.description = desc
        embed.set_author(
            name=f"Stratagem Roulette with {rolls} roll{'s' if rolls > 1 else ''}"
        )
        await ctx.send(embed=embed)


async def setup(bot):
    module_name = "cogs.HD2"
    try:
        importlib.reload(hd2)
        gui.gprint(f"{module_name} reloaded successfully.")
    except ImportError:
        gui.gprint(f"Failed to reload {module_name}.")
    await bot.add_cog(HelldiversCog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversCog")
