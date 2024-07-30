import asyncio
import csv
import importlib
import json
import datetime
from typing import Dict, List, Literal

import discord
from dateutil.rrule import MINUTELY, SU, WEEKLY, rrule
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

import cogs.HD2 as hd2
import gui
from assetloader import AssetLookup

# import datetime
from bot import (
    Guild_Task_Functions,
    StatusEditMessage,
    TC_Cog_Mixin,
    TCBot,
    TCGuildTask,
)
from utility import WebhookMessageWrapper as web
from bot.Tasks import TCTask, TCTaskManager
from utility import MessageTemplates, load_json_with_substitutions, urltomessage
from utility.embed_paginator import pages_of_embeds, pages_of_embeds_2

from .HD2.db import ServerHDProfile



class HelldiversMathCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""


    def __init__(self, bot):
        self.bot: TCBot = bot
        self.loghook = AssetLookup.get_asset("loghook", "urls")
        self.get_running=False
        # self.session=aiohttp.ClientSession()
        

        nowd = datetime.datetime.now()
        st = datetime.datetime(
            nowd.year, nowd.month, nowd.day, nowd.hour, int(nowd.minute // 2) * 2, 
        )
        robj2 = rrule(freq=MINUTELY, interval=1, dtstart=st)
        self.QueueAll=asyncio.Queue()
        if not TCTaskManager.does_task_exist("UpdateLog"):
            self.tc_task2 = TCTask("UpdateLog", robj2, robj2.after(st))
            self.tc_task2.assign_wrapper(self.updatelog)
        self.run.start()

    def cog_unload(self):
        TCTaskManager.remove_task("UpdateLog")
        self.run.cancel()

    @tasks.loop(seconds=2)
    async def run(self):
        try:
            item = self.QueueAll.get_nowait()
        except asyncio.QueueEmpty:
            return
        event_type = item['mode']
        place = item['place']
        value = item['value']
        embed = None

        if event_type == 'new':
            if place == 'campaign':
                embed = hd2.embeds.campaignLogEmbed(value, self.apistatus.planets.get(int(value.planetIndex), None), "started")
            elif place == 'planetAttacks':
                embed = hd2.embeds.planetAttackEmbed(value, self.apistatus.planets, "started")
            elif place == 'planetevents':
                embed = hd2.embeds.planetEventEmbed(value, self.apistatus.planets.get(int(value.planetIndex), None), "started")
            elif place == 'globalEvents':
                embed = hd2.embeds.globalEventEmbed(value, "started")
            elif place == 'news':
                embed = hd2.embeds.NewsFeedEmbed(value, "started")
        elif event_type == 'remove':
            if place == 'campaign':
                embed = hd2.embeds.campaignLogEmbed(value, self.apistatus.planets.get(int(value.planetIndex), None), "ended")
            elif place == 'planetAttacks':
                embed = hd2.embeds.planetAttackEmbed(value, self.apistatus.planets, "ended")
            elif place == 'planetevents':
                embed = hd2.embeds.planetEventEmbed(value, self.apistatus.planets.get(int(value.planetIndex), None), "ended")
            elif place == 'globalEvents':
                embed = hd2.embeds.globalEventEmbed(value, "ended")
            elif place == 'news':
                embed = hd2.embeds.NewsFeedEmbed(value, "ended")
        elif event_type == 'change':
            (info, dump) = value
            if place == 'planets' or place == 'planetInfos':
                planet = self.apistatus.planets.get(int(info.index), None)
                if planet:
                    embed = hd2.embeds.dumpEmbedPlanet(info, dump, planet, "changed")
                else:
                    embed = hd2.embeds.dumpEmbed(info, dump, "planet","changed")
            elif place == 'stats_raw':
                embed = hd2.embeds.dumpEmbed(info, dump, 'stats', "changed")
            elif place == 'info_raw':
                embed = hd2.embeds.dumpEmbed(info, dump, 'info', "changed")

        if embed:
            print(embed.description)
            await web.postMessageAsWebhookWithURL(
                self.loghook,
                message_content="",
                display_username="Super Earth Event Log",
                avatar_url=self.bot.user.avatar.url,
                embed=[embed],
            )

    @run.error
    async def logerror(self,ex):
       await self.bot.send_error(ex, "LOG ERROR", True)

    async def updatelog(self):
        try:
            if not self.get_running:
                task=asyncio.create_task(self.load_log())
            else:
                print("NOT SCHEDULING.")

        except Exception as e:
            await self.bot.send_error(e, "LOG ERROR", True)


    async def load_log(self):
        try:
            await asyncio.wait_for(self.main_log(), timeout=60)
        except Exception as e:
            await self.bot.send_error(e, "LOG ERROR", True)
            self.get_running=False

    async def main_log(self):
        self.get_running=True
        lastwar=hd2.helldive.models.DiveharderAll(**self.apistatus.warall.model_dump())
        nowval, warstat = await self.apistatus.get_now(lastwar,self.QueueAll)

        if nowval:
            pass

        self.apistatus.warall = warstat
        self.get_running = False



    @commands.is_owner()
    @commands.command(name="now_test")
    async def load_test_now(self, ctx: commands.Context):
        await self.load_log()
        await ctx.send("Done testing now.")
    
    @commands.is_owner()
    @commands.command(name="now_test")
    async def load_test_now(self, ctx: commands.Context):
        await self.load_log()
        await ctx.send("Done testing now.")

    @property
    def apistatus(self) -> hd2.ApiStatus:
        return self.bot.get_cog("HelldiversCog").apistatus

    async def campaign_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """
        Autocomplete for planet lookup.  Search by either the name or index.
        """
        items = (l.get_first().planet for l in self.apistatus.campaigns.values())
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

    calc = app_commands.Group(name="hd2_calc", description="Commands for mathdiving.")

    @calc.command(
        name="players_for_dps",
        description="estimate players needed to get a target dps on a specific planet",
    )
    @app_commands.autocomplete(byplanet=campaign_autocomplete)
    @app_commands.describe(dps="damage per second")
    async def players_for_dps(
        self, interaction: discord.Interaction, dps: float, byplanet: int
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)

        embeds = []
        mp_mult = self.apistatus.war.get_first().impactMultiplier
        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            eps = hd2.maths.dps_to_eps(dps, planet.regenPerSecond, mp_mult)
            play, conf = hd2.predict_needed_players(eps, mp_mult)
            embeds.append(
                hd2.create_planet_embed(
                    planet, cstr=None, last=None, stat=self.apistatus
                )
            )
            await ctx.send(
                f"Need `{play}` players to achieve dps of `{dps}` on {planet.get_name()}."
                + f"\n standard error `{conf}`.",
                ephemeral=True,
            )
            # await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)
        else:
            await ctx.send("Planet not found.", ephemeral=True)

    @calc.command(
        name="players_for_lph",
        description="estimate players needed to get a target lph on a specific planet",
    )
    @app_commands.autocomplete(byplanet=campaign_autocomplete)
    @app_commands.describe(lph="liberation percent per hour")
    async def players_for_lph(
        self, interaction: discord.Interaction, lph: float, byplanet: int
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)

        embeds = []
        mp_mult = self.apistatus.war.get_first().impactMultiplier
        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            dps = hd2.maths.lph_to_dps(lph, planet.maxHealth)
            eps = hd2.maths.dps_to_eps(dps, planet.regenPerSecond, mp_mult)
            play, conf = hd2.predict_needed_players(eps, mp_mult)
            embeds.append(
                hd2.create_planet_embed(
                    planet, cstr=None, last=None, stat=self.apistatus
                )
            )
            await ctx.send(
                f"Need `{play}` players to achieve lph of `{lph}({dps} dps)` on {planet.get_name()}."
                + f"\n standard error `{conf}`.",
                ephemeral=True,
            )
            # await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)
        else:
            await ctx.send("Planet not found.", ephemeral=True)

    @calc.command(
        name="dps_to_lph",
        description="Convert damage per second to liberation per hour.",
    )
    @app_commands.describe(dps="damage per second")
    @app_commands.describe(max_health="Max health of the planet or event.")
    async def dps_to_lph(
        self, interaction: discord.Interaction, dps: float, max_health: int
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        lps = hd2.maths.dps_to_lph(dps, max_health)
        await ctx.send(
            f"`{dps}` dps is about `{lps}` liberation per hour.", ephemeral=True
        )

    @calc.command(
        name="eps_to_dps",
        description="Convert experience per second to damage per second.",
    )
    @app_commands.describe(eps="experience per second")
    async def eps_to_dps(self, interaction: discord.Interaction, eps: float):
        ctx: commands.Context = await self.bot.get_context(interaction)
        war = self.apistatus.war.get_first()
        dps = war.impactMultiplier * eps
        lps = hd2.maths.dps_to_lph(dps, 1000000)
        await ctx.send(
            f"`{eps}` dps is about `{dps}` dps per second, and `{lps}` liberation per hour.",
            ephemeral=True,
        )

    @calc.command(
        name="impactdatacollection",
        description="Convert experience per second to damage per second.",
    )
    @app_commands.describe(imp="squad impact")
    @app_commands.describe(samples="total number of samples collected")
    @app_commands.describe(xp="mission xp total")
    @app_commands.describe(deaths="total number of deaths")
    @app_commands.describe(diff="mission difficulty")
    async def impactdc(
        self,
        interaction: discord.Interaction,
        imp: float,
        samples: int,
        xp: float,
        deaths: float,
        diff: int = 0,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        war = await self.apistatus.get_war_now()
        influence = war.impactMultiplier * imp
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        timestamp = int(now.timestamp())
        await ctx.send(
            f"`{imp}` impact (influence `{influence}` at mp_mult `{war.impactMultiplier}`), difficulty `{diff}`, `{samples}` samples,`{xp}` xp, `{deaths}` deaths. ",
            ephemeral=False,
        )
        row = {
            "timestamp": timestamp,
            "mp_mult": war.impactMultiplier,
            "impact": imp,
            "influence": influence,
            "samples": samples,
            "xp": xp,
            "diff": diff,
        }
        with open("sample_impact.csv", mode="a", newline="", encoding="utf8") as file:
            writer = csv.DictWriter(file, fieldnames=row.keys())

            # If the file is empty, write the header
            if file.tell() == 0:
                writer.writeheader()

            writer.writerow(row)


@app_commands.allowed_installs(guilds=False, users=True)
class HD2Local(
    app_commands.Group, name="hd2local", description="Helldivers Shortcut Commands"
):
    """Stub class"""


class HelldiversGlobalCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot

        self.globalonly = True
        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )
        # self.session=aiohttp.ClientSession()

    @property
    def apistatus(self) -> hd2.ApiStatus:
        return self.bot.get_cog("HelldiversCog").apistatus

    hd2user = HD2Local()

    @hd2user.command(
        name="get_overview", description="get the current game state from helldivers2"
    )
    async def get_overview(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        here = ""
        if self.apistatus.assignments:
            for i, assignment in self.apistatus.assignments.items():
                b, a = assignment.get_first_change()
                here = b.to_str()
        use = {"galactic_overview": {"value": [here]}}

        emb = hd2.campaign_view(self.apistatus, self.hd2)
        await ctx.send(embeds=[emb])


async def setup(bot):
    module_name = "cogs.HD2Math"
    HelldiversGlobalCog
    await bot.add_cog(HelldiversMathCog(bot))
    await bot.add_cog(HelldiversGlobalCog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversMathCog")

    await bot.remove_cog("HelldiversGlobalCog")
